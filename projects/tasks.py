import boto3

import yaml

from config.celery import app

from django.conf import settings
from django.utils import timezone

from projects.models import Change, Build, Task


def create_tasks(build):
    repository = GitHub(
            settings.GITHUB_USERNAME,
            password=settings.GITHUB_ACCESS_TOKEN
        ).repository(
            build.change.project.repository.owner.login,
            build.change.project.repository.name
        )
    content = repository.contents('beekeeper.yml', ref=build.commit.sha)
    if content is None:
        return ValueError("Repository doesn't contain BeeKeeper config file")

    config = yaml.load(content.decoded.decode('utf-8'))
    if build.change.change_type == Change.CHANGE_TYPE_PULL_REQUEST:
        phases = config['pull_request']
    elif build.change.change_type == Change.CHANGE_TYPE_PUSH:
        phases = config['push']

    for phase, phase_configs in enumerate(phases):
        for phase_name, phase_config in phase_configs.items():
            if 'task' in phase_config:
                print("Created phase %s task %s" % (phase, phase_name))
                task = Task.objects.create(
                    build=build,
                    name=phase_config.get('name', phase_name),
                    slug=phase_name,
                    phase=phase,
                    descriptor=phase_config['task'],
                )
            elif 'subtasks' in phase_config:
                for task_configs in phase_config['subtasks']:
                    for task_name, task_config in task_configs.items():
                        print("Created phase %s subtask %s" % (phase, phase_name))
                        task = Task.objects.create(
                            build=build,
                            name=task_config.get('name', task_name),
                            slug=task_name,
                            phase=phase,
                            descriptor=task_config['task'],
                        )
            else:
                print("Phase %s task %s doesn't contain a task or subtask descriptor" % (phase, phase_name))




@app.task(bind=True)
def check_build(self, build_pk):
    build = Build.objects.get(pk=build_pk)

    aws_session = boto3.session.Session(
        region_name=settings.AWS_ECS_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    ecs_client = aws_session.client('ecs')

    if build.status == Build.STATUS_CREATED:
        print("Starting build %s..." % build)
        # Record that the build has started.
        build.status = Build.STATUS_RUNNING
        build.save()

        # Retrieve task definition
        try:
            print("Creating task definitions...")
            create_tasks(build)

            # Start the tasks with no prerequisites
            print("Starting initial tasks...")
            initial_tasks = build.tasks.filter(status=Build.STATUS_CREATED, phase=0)
            if initial_tasks:
                for task in initial_tasks:
                    print("Starting task %s..." % task.name)
                    task.start(ecs_client)
            else:
                raise RuntimeError('No phase 0 tasks defined')
        except Exception as e:
            print("Error creating tasks: %s" % e)
            build.status = Build.STATUS_ERROR
            build.save()

    elif build.status == Build.STATUS_RUNNING:
        print("Checking status of build %s..." % build)
        # Check all currently running tasks
        started_tasks = build.tasks.started()
        if started_tasks:
            print("There are %s active tasks." % started_tasks.count())
            response = ecs_client.describe_tasks(
                 cluster=settings.AWS_ECS_CLUSTER_NAME,
                 tasks=[task.arn for task in started_tasks]
            )

            for task_response in response['tasks']:
                print('Task %s: %s' % (
                    task_response['taskArn'],
                    task_response['lastStatus'])
                )
                task = build.tasks.get(arn=task_response['taskArn'])
                if task_response['lastStatus'] == 'RUNNING':
                    task.status = Task.STATUS_RUNNING
                elif task_response['lastStatus'] == 'STOPPED':
                    task.status = Task.STATUS_DONE
                    task.completed = timezone.now()
                elif task_response['lastStatus'] == 'FAILED':
                    task.status = Task.STATUS_ERROR
                task.save()

        try:
            completed_phase = max(build.tasks.done().values_list('phase', flat=True))

            # Check for any tasks that are no longer blocked on prerequisites
            new_tasks = build.tasks.filter(
                            status=Task.STATUS_CREATED,
                            phase=completed_phase + 1
                        )
        except ValueError:
            new_tasks = []

        if new_tasks:
            print("Starting new tasks...")
            for task in new_tasks:
                print("Starting task %s..." % task.name)
                task.start(ecs_client)
        elif build.tasks.not_finished().exists():
            print("Still waiting on tasks to complete.")
        else:
            print("No more tasks pending.")
            if build.tasks.error().exists():
                build.status = Build.STATUS_ERROR
                build.result = Build.RESULT_FAILED
            else:
                build.status = Build.STATUS_DONE
                build.result = min(t.result for t in build.tasks.all())

            build.save()
            print("Build status %s" % build.get_status_display())
            print("Build result %s" % build.get_result_display())

    elif build.status == Build.STATUS_STOPPING:
        print("Stopping build %s..." % build)
        running_tasks = build.tasks.running()
        stopping_tasks = build.tasks.stopping()
        if running_tasks:
            print("There are %s active tasks." % started_tasks.count())
            for task in running_tasks:
                task.stop(ecs_client)
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
