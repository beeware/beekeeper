from datetime import timedelta

import boto3

from github3 import GitHub

import yaml

from config.celery import app

from django.conf import settings
from django.utils import timezone
from django.utils.timesince import timesince

from projects.models import Change, Build
from aws.models import Task


def load_task_configs(config):
    task_data = []
    for phase, phase_configs in enumerate(config):
        for phase_name, phase_config in phase_configs.items():
            if 'subtasks' in phase_config:
                for task_configs in phase_config['subtasks']:
                    for task_name, task_config in task_configs.items():
                        # If a descriptor is provided at the subtask level,
                        # use it; otherwise use the phase's task definition.
                        descriptor = None
                        if task_config:
                            descriptor = task_config.get('task', None)
                        if descriptor is None:
                            descriptor = phase_config.get('task', None)
                        if descriptor is None:
                            raise ValueError("Subtask %s in phase %s task %s doesn't contain a task descriptor." % (
                                task_name, phase, phase_name
                            ))

                        # The environment is the phase environment, overridden
                        # by the task environment.
                        task_env = phase_config.get('environment', {}).copy()
                        if task_config:
                            task_env.update(task_config.get('environment', {}))
                            task_profile = task_config.get('profile', phase_config.get('profile', 'default'))

                            full_name = task_config.get('name', task_name)
                        else:
                            full_name = task_name
                            task_profile = 'default'

                        task_data.append({
                            'name': full_name,
                            'slug': "%s:%s" % (phase_name, task_name),
                            'phase': phase,
                            'is_critical': task_config.get('critical', True),
                            'environment': task_env,
                            'profile_slug': task_profile,
                            'descriptor': descriptor,
                        })

            elif 'task' in phase_config:
                task_data.append({
                    'name': phase_config.get('name', phase_name),
                    'slug': phase_name,
                    'phase': phase,
                    'is_critical': phase_config.get('critical', True),
                    'environment': phase_config.get('environment', {}),
                    'profile_slug': phase_config.get('profile', 'default'),
                    'descriptor': phase_config['task'],
                })
            else:
                raise ValueError("Phase %s task %s doesn't contain a task or subtask descriptor." % (
                    phase, phase_name
                ))
    return task_data


def create_tasks(gh_repo, build):
    # Download the config file from Github.
    content = gh_repo.contents('beekeeper.yml', ref=build.commit.sha)
    if content is None:
        raise ValueError("Repository doesn't contain BeeKeeper config file.")

    # Parse the raw configuration content and extract the appropriate phase.
    config = yaml.load(content.decoded.decode('utf-8'))
    if build.change.change_type == Change.CHANGE_TYPE_PULL_REQUEST:
        phases = config.get('pull_request', [])
    elif build.change.change_type == Change.CHANGE_TYPE_PUSH:
        phases = config.get('push', [])

    # Parse the phase configuration and create tasks
    for task_config in load_task_configs(phases):
        print("Created phase %(phase)s task %(name)s" % task_config)
        task = Task.objects.create(
            build=build,
            **task_config
        )
        task.report(gh_repo)


def on_check_build_failure(self, exc, task_id, args, kwargs, einfo):
    build = Build.objects.get(pk=args[0])
    print("Error checking build %s: %s" % (build, str(exc)))
    build.status = Build.STATUS_ERROR
    build.error = str(exc)
    build.save()


@app.task(
    bind=True,
    on_failure=on_check_build_failure
)
def check_build(self, build_pk):
    build = Build.objects.get(pk=build_pk)

    aws_session = boto3.session.Session(
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    ecs_client = aws_session.client('ecs')
    ec2_client = aws_session.client('ec2')

    gh_session = GitHub(
            settings.GITHUB_USERNAME,
            password=settings.GITHUB_ACCESS_TOKEN
        )
    gh_repo = gh_session.repository(
            build.change.project.repository.owner.login,
            build.change.project.repository.name
        )

    if build.status == Build.STATUS_CREATED:
        print("Starting build %s..." % build)
        # Record that the build has started.
        build.status = Build.STATUS_RUNNING
        build.save()

        # Retrieve task definition
        print("Creating task definitions...")
        create_tasks(gh_repo, build)

        # Start the tasks with no prerequisites
        print("Starting initial tasks...")
        initial_tasks = build.tasks.filter(status=Build.STATUS_CREATED, phase=0)
        if initial_tasks:
            for task in initial_tasks:
                print("Starting task %s..." % task.name)
                task.start(ecs_client, ec2_client)
        else:
            raise ValueError("No phase 0 tasks defined for build type '%s'" % build.change.change_type)

    elif build.status == Build.STATUS_RUNNING:
        print("Checking status of build %s..." % build)
        # Update the status of all currently running tasks
        started_tasks = build.tasks.started()
        if started_tasks:
            print("There are %s active tasks." % started_tasks.count())
            # Only check the *running* tasks - the ones where we have an ARN
            running_arns = [task.arn for task in started_tasks if task.arn]
            pending_tasks = [task for task in started_tasks if task.arn is None]

            if pending_tasks:
                for task in pending_tasks:
                    print('Task %s: pending for %s' % (
                        task, timesince(task.pending)
                    ))
                    if timezone.now() - task.pending < timedelta(seconds=300):
                        print('   Trying to start again...')
                        task.start(ecs_client, ec2_client)
                    else:
                        print('   Killing task...')
                        task.status = Task.STATUS_ERROR
                        task.error = "Timeout waiting for task to start."
                        task.save()

            if running_arns:
                response = ecs_client.describe_tasks(
                     cluster=settings.AWS_ECS_CLUSTER_NAME,
                     tasks=running_arns
                )

                for task_response in response['tasks']:
                    print('Task %s: %s' % (
                        task_response['taskArn'],
                        task_response['lastStatus'])
                    )
                    print('Full response: %s' % task_response)

                    task = build.tasks.get(arn=task_response['taskArn'])
                    if task_response['lastStatus'] == 'RUNNING':
                        task.status = Task.STATUS_RUNNING
                    elif task_response['lastStatus'] == 'STOPPED':
                        if all('exitCode' in container for container in task_response['containers']):
                            task.status = Task.STATUS_DONE

                            # Determine the status of the task
                            failed_containers = [
                                container['name']
                                for container in task_response['containers']
                                if container['exitCode'] != 0
                            ]
                            if failed_containers:
                                if task.is_critical:
                                    task.result = Build.RESULT_FAIL
                                else:
                                    task.result = Build.RESULT_NON_CRITICAL_FAIL
                            else:
                                task.result = Build.RESULT_PASS

                            # Report the status to Github.
                            task.report(gh_repo)

                            # Record the completion time.
                            task.completed = timezone.now()
                        else:
                            # A container didn't have a status code; that means a
                            # pre-start failure.
                            task.status = Task.STATUS_ERROR
                            task.error = '; '.join(
                                container.get('reason')
                                for container in task_response['containers']
                                if container.get('reason')
                            )
                    elif task_response['lastStatus'] == 'FAILED':
                        task.status = Task.STATUS_ERROR
                        task.error = "AWS task failure."
                    elif task_response['lastStatus'] != 'PENDING':
                        raise ValueError('Unknown task status %s' % task_response['lastStatus'])
                    task.save()

        # If there are still tasks running, wait for them to finish.
        unfinished_tasks = build.tasks.not_finished()
        if unfinished_tasks.exists():
            running_phase = max(unfinished_tasks.values_list('phase', flat=True))
            print("Still waiting for tasks in phase %s to complete." % running_phase)
        else:
            # There are no unfinished tasks.
            # If there have been any failures or task errors, stop right now.
            # Otherwise, queue up tasks for the next phase.
            finished_tasks = build.tasks.finished()
            finished_phase = max(finished_tasks.values_list('phase', flat=True))

            if finished_tasks.error().exists():
                print("Errors encountered during phase %s" % finished_phase)
                new_tasks = None
                build.status = Build.STATUS_ERROR
                build.result = Build.RESULT_FAIL
                build.error = "%s tasks generated errors" % build.tasks.error().count()
            elif finished_tasks.failed().exists():
                print("Failures encountered during phase %s" % finished_phase)
                new_tasks = None
                build.status = Build.STATUS_DONE
                build.result = Build.RESULT_FAIL
            else:
                new_tasks = build.tasks.filter(
                                status=Task.STATUS_CREATED,
                                phase=finished_phase + 1
                            )

            if new_tasks:
                print("Starting new tasks...")
                for task in new_tasks:
                    print("Starting task %s..." % task.name)
                    task.start(ecs_client, ec2_client)
            elif new_tasks is None:
                print("Build aborted.")
                build.save()
            else:
                print("No new tasks required.")
                build.status = Build.STATUS_DONE
                build.result = min(
                    t.result
                    for t in build.tasks.all()
                    if t.result != Build.RESULT_PENDING
                )

                build.save()
                print("Build status %s" % build.get_status_display())
                print("Build result %s" % build.get_result_display())

    elif build.status == Build.STATUS_STOPPING:
        print("Stopping build %s..." % build)
        running_tasks = build.tasks.running()
        stopping_tasks = build.tasks.stopping()
        if running_tasks:
            print("There are %s active tasks." % running_tasks.count())
            for task in running_tasks:
                task.stop(ecs_client=ecs_client)
        elif stopping_tasks:
            response = ecs_client.describe_tasks(
                 cluster=settings.AWS_ECS_CLUSTER_NAME,
                 tasks=[task.arn for task in stopping_tasks]
            )

            for task_response in response['tasks']:
                print('Task %s: %s' % (
                    task_response['taskArn'],
                    task_response['lastStatus'])
                )
                print('Full response: %s' % task_response)

                task = build.tasks.get(arn=task_response['taskArn'])
                if task_response['lastStatus'] == 'STOPPED':
                    task.status = Task.STATUS_STOPPED
                elif task_response['lastStatus'] == 'FAILED':
                    task.status = Task.STATUS_ERROR
                elif task_response['lastStatus'] != 'RUNNING':
                    print(" - don't know how to handle this status")
                task.save()
        else:
            print("There are no tasks running; Build %s has been stopped." % build)
            build.status = Build.STATUS_STOPPED
            build.save()

    if build.status not in (Build.STATUS_DONE, Build.STATUS_ERROR, Build.STATUS_STOPPED):
        print("Schedule another build check...")
        check_build.apply_async((build_pk,), countdown=5)

    print("Build check complete.")


def on_sweeper_failure(self, exc, task_id, args, kwargs, einfo):
    task = Task.objects.get(pk=args[0])
    print("Error sweeping task %s:%s: %s" % (task.build, task, str(exc)))
    task.status = Task.STATUS_ERROR
    task.save()


@app.task(
    bind=True,
    on_failure=on_sweeper_failure
)
def sweeper(self, task_pk):
    task = Task.objects.get(pk=task_pk)
    print("Sweeping %s:%s..." % (task.build, task))

    aws_session = boto3.session.Session(
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    ec2_client = aws_session.client('ec2')

    if task.is_finished:
        profile = task.profile
        if task.updated + timedelta(seconds=profile.cooldown) < timezone.now():
            print("Task %s:%s has exceeded cooldown period." % (
                task.build, task
            ))
            active_instances = task.instances.active()
            if active_instances:
                for instance in active_instances:
                    print("Checking %s for activity..." % instance)
                    most_recent_task = instance.tasks.latest('updated')
                    if task == most_recent_task:
                        print("Task %s:%s is the most recent task on %s; consider terminating instance." % (
                            task.build, task, instance
                        ))
                        terminated = instance.terminate(ec2_client=ec2_client)
                        if terminated:
                            print("Instance %s terminated." % instance)
                        else:
                            print("Need to preserve %s %s instances; not terminating %s." % (
                                instance.profile.min_instances, instance.profile, instance
                            ))
                    else:
                        print("%s has been used recently (most recently by %s:%s)." % (
                            instance, task.build, task
                        ))
            else:
                print("None of the instances associated with %s:%s are still active." % (
                    task.build, task
                ))
        else:
            print("Task %s:%s has been updated (possibly restarted and re-finished). No sweeping required." % (
                task.build, task
            ))
    else:
        print("Task %s:%s has been updated (possibly restarted). No sweeping required." % (
            task.build, task
        ))


def on_reaper_failure(self, exc, task_id, args, kwargs, einfo):
    task = Task.objects.get(pk=args[0])
    print("Error reaping task %s:%s: %s" % (task.build, task, str(exc)))
    task.status = Build.STATUS_ERROR
    task.save()


@app.task(
    bind=True,
    on_failure=on_reaper_failure
)
def reaper(self, task_pk):
    task = Task.objects.get(pk=task_pk)
    print("Checking if %s:%s has finished..." % (task.build, task))

    if task.is_finished:
        print("Task %s:%s has finished.")
    else:
        profile = task.profile
        if task.started + timedelta(seconds=profile.timeout) < timezone.now():
            print("Task %s:%s has exceeded maximum duration for profile %s; terminating" % (
                task.build, task, profile
            ))
            task.stop()
        else:
            print("Task %s:%s has been restarted." % (
                task.build, task
            ))

