from django.db import models
from django.urls import reverse
from django.utils import timezone

from github.models import Repository, PullRequest


class ProjectQuerySet(models.QuerySet):
    def pending_approval(self):
        return self.filter(status=Project.STATUS_NEW)

    def active(self):
        return self.filter(status=Project.STATUS_ACTIVE)

    def attic(self):
        return self.filter(status=Project.STATUS_ATTIC)


class Project(models.Model):
    STATUS_NEW = 10
    STATUS_ACTIVE = 100
    STATUS_ATTIC = 1000
    STATUS_IGNORED = 9999

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ATTIC, 'Attic'),
        (STATUS_IGNORED, 'Ignored'),
    ]

    objects = ProjectQuerySet.as_manager()

    repository = models.OneToOneField(Repository)
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_NEW)

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('repository__name',)

    def __str__(self):
        return self.repository.full_name

    def get_absolute_url(self):
        return reverse('projects:project', kwargs={
                'owner': self.repository.owner.login,
                'repo_name': self.repository.name,
            })


class BuildQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status__in=(
                    Build.STATUS_CREATED, Build.STATUS_RUNNING)
                )


class Build(models.Model):
    STATUS_CREATED = 10
    STATUS_RUNNING = 20
    STATUS_DONE = 100
    STATUS_CANCELLED = 9999

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    RESULT_PENDING = 0
    RESULT_FAIL = 10
    RESULT_QUALIFIED_PASS = 19
    RESULT_PASS = 20
    RESULT_CHOICES = [
        (RESULT_PENDING, 'Pending'),
        (RESULT_FAIL, 'Fail'),
        (RESULT_QUALIFIED_PASS, 'Qualified pass'),
        (RESULT_PASS, 'Pass'),
    ]
    objects = BuildQuerySet.as_manager()

    project = models.ForeignKey(Project, related_name='builds')
    pull_request = models.ForeignKey(PullRequest, related_name='builds')
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
    result = models.IntegerField(choices=RESULT_CHOICES, default=RESULT_PENDING)

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def get_absolute_url(self):
        return reverse('projects:build', kwargs={
                'owner': self.project.repository.owner.login,
                'repo_name': self.project.repository.name,
                'pr': self.pull_request.number,
                'build_pk': self.pk
            })

    def cancel(self):
        if self.status == Build.STATUS_RUNNING:
            print("kill build...")

        self.status = Build.STATUS_CANCELLED
        self.save()
