import uuid

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
                    Task.STATUS_CREATED,
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
    started = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    environment = postgres.JSONField()
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
            # ...
        }
        environment.update(self.environment)

        response = ecs_client.run_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            taskDefinition=self.descriptor,
            overrides={
                'containerOverrides': [
                    {
                        'name': self.descriptor,
                        'environment': [
                            {
                                'name': key,
                                'value': value
                            }
                            for key, value in environment
                        ],
                    }
                ]
            }
        )
        self.arn = response['tasks'][0]['taskArn']
        self.status = Task.STATUS_PENDING
        self.started = timezone.now()
        self.save()

    def stop(self, ecs_client):
        response = ecs_client.stop_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            task=self.arn
        )
        self.status = Task.STATUS_STOPPING
        self.save()
