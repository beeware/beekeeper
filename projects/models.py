import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from github import models as github


class StatusQuerySet(models.QuerySet):
    def pending_approval(self):
        return self.filter(status=Project.STATUS_NEW)

    def active(self):
        return self.filter(status=Project.STATUS_ACTIVE)

    def attic(self):
        return self.filter(status=Project.STATUS_ATTIC)

    def ignored(self):
        return self.filter(status=Project.STATUS_IGNORED)


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

    objects = StatusQuerySet.as_manager()
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_NEW)

    repository = models.OneToOneField(github.Repository, related_name='project')

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('repository__name',)

    def __str__(self):
        return self.repository.name

    def get_absolute_url(self):
        return reverse('projects:project', kwargs={
                'owner': self.repository.owner.login,
                'repo_name': self.repository.name,
            })

    @property
    def current_commit(self):
        try:
            return self.repository.commits.latest('created')
        except Commit.DoesNotExist:
            return None

    @property
    def builds(self):
        return Build.objects.filter(change__project=self)


class Change(models.Model):
    CHANGE_TYPE_PULL_REQUEST = 10
    CHANGE_TYPE_PUSH = 20
    CHANGE_TYPE_CHOICES = [
        (CHANGE_TYPE_PULL_REQUEST, 'Pull Request'),
        (CHANGE_TYPE_PUSH, 'Push'),
    ]

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

    objects = StatusQuerySet.as_manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    change_type = models.IntegerField(choices=CHANGE_TYPE_CHOICES)

    project = models.ForeignKey(Project, related_name='changes')
    pull_request = models.ForeignKey(github.PullRequest, null=True, blank=True, related_name='changes')
    push = models.ForeignKey(github.Push, null=True, blank=True, related_name='changes')

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('project__repository__name', '-created')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('projects:change', kwargs={
                    'owner': self.project.repository.owner.login,
                    'repo_name': self.project.repository.name,
                    'change_pk': str(self.pk),
                })

    @property
    def title(self):
        if self.pull_request:
            return 'PR #%s' % self.pull_request.number
        else:
            return self.push.commit.display_sha

    @property
    def description(self):
        if self.pull_request:
            return self.pull_request.title
        else:
            return self.push.commit.message

    @property
    def user(self):
        if self.pull_request:
            return self.pull_request.user
        else:
            return self.push.commit.user

    def complete(self):
        self.status = Change.STATUS_ATTIC
        self.completed = timezone.now()
        self.save()

        for build in self.builds.pending():
            build.cancel()


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    change = models.ForeignKey(Change, related_name='builds')
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
    result = models.IntegerField(choices=RESULT_CHOICES, default=RESULT_PENDING)

    commit = models.ForeignKey(github.Commit, related_name='builds')

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def get_absolute_url(self):
        return reverse('projects:build', kwargs={
                    'owner': self.change.project.repository.owner.login,
                    'repo_name': self.change.project.repository.name,
                    'change_pk': str(self.change.pk),
                    'build_pk': str(self.pk)
                })

    @property
    def display_pk(self):
        return self.id.hex[:8]

    def cancel(self):
        if self.status == Build.STATUS_RUNNING:
            print("kill build...")

        self.status = Build.STATUS_CANCELLED
        self.save()
