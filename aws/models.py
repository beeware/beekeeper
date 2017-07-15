import uuid

from github3.exceptions import GitHubError

from django.conf import settings
from django.contrib.postgres import fields as postgres
from django.db import models
from django.urls import reverse
from django.utils import timezone

from projects.models import Build



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
    overrides = postgres.JSONField()
    descriptor = models.CharField(max_length=100)
    arn = models.CharField(max_length=100, null=True, blank=True)

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
    def log_stream_name(self):
        return '%s/%s/%s' % (
            self.descriptor, self.descriptor, self.arn.rsplit('/', 1)[1]
        )

    def start(self, ecs_client):
        environment = {
            'GITHUB_OWNER': self.build.commit.repository.owner.login,
            'GITHUB_PROJECT_NAME': self.build.commit.repository.name,
            'GITHUB_USERNAME': settings.GITHUB_USERNAME,
            'GITHUB_ACCESS_TOKEN': settings.GITHUB_ACCESS_TOKEN,
            'GITHUB_PR_NUMBER': self.build.change.pull_request.number if self.build.change.is_pull_request else None,
            'SHA': self.build.commit.sha,
            'TASK': self.slug.split(':')[-1]
        }
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
        container_definition.update(self.overrides)

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
