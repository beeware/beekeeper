import uuid

from github3.exceptions import GitHubError

from django.conf import settings
from django.contrib.postgres import fields as postgres
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from projects.models import Build, Variable



class TaskQuerySet(models.QuerySet):
    def started(self):
        return self.filter(status__in=(
                    Task.STATUS_PENDING,
                    Task.STATUS_RUNNING,
                ))

    def not_finished(self):
        return self.filter(status__in=(
                    Task.STATUS_PENDING,
                    Task.STATUS_RUNNING,
                    Task.STATUS_STOPPING,
                ))

    def pending(self):
        return self.filter(status=Task.STATUS_PENDING)

    def running(self):
        return self.filter(status=Task.STATUS_RUNNING)

    def stopping(self):
        return self.filter(status=Task.STATUS_STOPPING)

    def finished(self):
        return self.filter(status__in=[
                                Task.STATUS_DONE,
                                Task.STATUS_ERROR,
                                Task.STATUS_STOPPED,
                            ])

    def done(self):
        return self.filter(status=Task.STATUS_DONE)

    def error(self):
        return self.filter(status=Task.STATUS_ERROR)

    def failed(self):
        return self.filter(result=Build.RESULT_FAIL)


class Task(models.Model):
    STATUS_CREATED = Build.STATUS_CREATED
    STATUS_PENDING = Build.STATUS_PENDING
    STATUS_RUNNING = Build.STATUS_RUNNING
    STATUS_DONE = Build.STATUS_DONE
    STATUS_ERROR = Build.STATUS_ERROR
    STATUS_STOPPING = Build.STATUS_STOPPING
    STATUS_STOPPED = Build.STATUS_STOPPED

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
        (STATUS_STOPPING, 'Stopping'),
        (STATUS_STOPPED, 'Stopped'),
    ]
    objects = TaskQuerySet.as_manager()

    build = models.ForeignKey(Build, related_name='tasks')
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
    result = models.IntegerField(choices=Build.RESULT_CHOICES, default=Build.RESULT_PENDING)

    name = models.CharField(max_length=100, db_index=True)
    slug = models.CharField(max_length=100, db_index=True)

    phase = models.IntegerField()
    is_critical = models.BooleanField()
    started = models.DateTimeField(null=True, blank=True)
    pending = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    environment = postgres.JSONField()
    profile = models.CharField(max_length=100, null=True)
    descriptor = models.CharField(max_length=100)
    arn = models.CharField(max_length=100, null=True, blank=True)

    error = models.TextField(blank=True)

    class Meta:
        ordering = ('phase', 'name',)
        unique_together = [('build', 'slug')]

    def get_absolute_url(self):
        return reverse('projects:task', kwargs={
                    'owner': self.build.change.project.repository.owner.login,
                    'repo_name': self.build.change.project.repository.name,
                    'change_pk': str(self.build.change.pk),
                    'build_pk': str(self.build.pk),
                    'task_slug': self.slug
                })

    def get_status_url(self):
        return reverse('projects:task-status', kwargs={
                    'owner': self.build.change.project.repository.owner.login,
                    'repo_name': self.build.change.project.repository.name,
                    'change_pk': str(self.build.change.pk),
                    'build_pk': str(self.build.pk),
                    'task_slug': self.slug
                })

    def __str__(self):
        return self.name

    @property
    def has_started(self):
        return self.status in [
            Task.STATUS_RUNNING,
            Task.STATUS_DONE,
            Task.STATUS_ERROR,
        ]

    @property
    def is_finished(self):
        return self.status in (
            Task.STATUS_DONE,
            Task.STATUS_ERROR,
            Task.STATUS_STOPPED
        )

    @property
    def has_error(self):
        return self.status == Task.STATUS_ERROR

    @property
    def log_stream_name(self):
        return '%s/%s/%s' % (
            self.descriptor, self.descriptor, self.arn.rsplit('/', 1)[1]
        )

    def full_status_display(self):
        if self.status == Task.STATUS_ERROR:
            return "Error: %s" % self.error
        elif self.status == Task.STATUS_PENDING:
            return "Pending (for %s)" % timesince(self.pending)
        elif self.status == Task.STATUS_RUNNING:
            return "Running (for %s)" % timesince(self.started)
        else:
            return self.get_status_display()

    def start(self, ecs_client, ec2_client):
        if self.build.change.is_pull_request:
            pr_number = self.build.change.pull_request.number
        else:
            pr_number = ''

        prev_success = self.build.previous_success
        if prev_success:
            last_success_sha = prev_success.commit.sha
        else:
            last_success_sha = ''

        environment = {
            'GITHUB_OWNER': self.build.commit.repository.owner.login,
            'GITHUB_PROJECT_NAME': self.build.commit.repository.name,
            'GITHUB_PR_NUMBER': pr_number,
            'CODE_URL': self.build.get_code_url(),
            'LAST_SUCCESS_SHA': last_success_sha,
            'SHA': self.build.commit.sha,
            'TASK': self.slug.split(':')[-1],
        }

        # Add environment variables from the project configuration.
        # Include, in order:
        #  * Global variables for all tasks
        #  * Global variables for a specific task
        #  * Project variables for all tasks
        #  * Project variables for a specific task
        for project in [None, self.build.change.project]:
            for descriptor in ['*', self.descriptor]:
                for key, value in Variable.objects.filter(project=project, descriptor=descriptor):
                    environment[key] = value

        # Add environment variables from the task configuration
        environment.update(self.environment)

        container_definition = {
            'name': self.descriptor,
            'environment': [
                {
                    'name': str(key),
                    'value': str(value)
                }
                for key, value in environment.items()
            ],
        }

        if self.profile == 'hi-cpu':
            container_definition.update({
                'cpu': 8192
            })

        response = ecs_client.run_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            taskDefinition=self.descriptor,
            overrides={
                'containerOverrides': [container_definition]
            }
        )
        if response['tasks']:
            self.arn = response['tasks'][0]['taskArn']
            self.status = Task.STATUS_PENDING
            self.pending = timezone.now()
            self.started = timezone.now()
            self.save()
        elif response['failures'][0]['reason'] in ['RESOURCE:CPU']:
            if self.status == Task.STATUS_CREATED:
                print("Spawning new c4.2xlarge instance...")
                ec2_client.run_instances(
                    ImageId=settings.AWS_ECS_AMI,
                    InstanceType='c4.2xlarge',
                    MinCount=1,
                    MaxCount=1,
                    KeyName='rkm',
                    SecurityGroupIds=settings.AWS_ECS_SECURITY_GROUP_IDS.split(':'),
                    SubnetId=settings.AWS_ECS_SUBNET_ID,
                    IamInstanceProfile={
                        "Name": "ecsInstanceRole"
                    },
                    UserData="#!/bin/bash \n echo ECS_CLUSTER=%s >> /etc/ecs/ecs.config" % settings.AWS_ECS_CLUSTER_NAME
                )

                self.status = Task.STATUS_PENDING
                self.pending = timezone.now()
                self.save()
        else:
            raise RuntimeError('Unable to start worker: %s' % response['failures'][0]['reason'])

    def stop(self, ecs_client):
        response = ecs_client.stop_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            task=self.arn
        )
        self.status = Task.STATUS_STOPPING
        self.save()

    def report(self, gh_repo):
        """Report the status of this task to GitHub

        gh_repo: An active GitHub API session.
        """
        gh_commit = gh_repo.commit(self.build.commit.sha)
        url = gh_commit._api.replace('commits', 'statuses')
        payload = {
            'context': '%s:%s/%s' % (settings.BEEKEEPER_NAMESPACE, self.phase, self.slug),
            'state': {
                Build.RESULT_PENDING: 'pending',
                Build.RESULT_FAIL: 'failure',
                Build.RESULT_NON_CRITICAL_FAIL: 'success',
                Build.RESULT_PASS: 'success',
            }[self.result],
            'target_url': settings.BEEKEEPER_URL + self.get_absolute_url(),
            'description': {
                Build.RESULT_PENDING: '%s pending...' % self.name,
                Build.RESULT_FAIL: '%s failed! Click for details.' % self.name,
                Build.RESULT_NON_CRITICAL_FAIL: '%s: non-critical problem found. Click for details.' % self.name,
                Build.RESULT_PASS: '%s passed.' % self.name,
            }[self.result],
        }
        response = gh_commit._post(url, payload)
        if not response.ok:
            raise GitHubError(response.reason)
