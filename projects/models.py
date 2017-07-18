import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from github import models as github

from .signals import start_build


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

    def get_shield_url(self):
        return reverse('projects:project-shield', kwargs={
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

    @property
    def pushes(self):
        return Change.objects.filter(change_type=Change.CHANGE_TYPE_PUSH)

    @property
    def pull_requests(self):
        return Change.objects.filter(change_type=Change.CHANGE_TYPE_PULL_REQUEST)

    def current_build(self, branch_name):
        try:
            return Build.objects.filter(
                    change__project=self,
                    change__change_type=Change.CHANGE_TYPE_PUSH,
                    commit__branch_name=branch_name,
                ).finished().latest('created')
        except (Change.DoesNotExist, Build.DoesNotExist):
            return None

    def approve(self):
        self.status = Project.STATUS_ACTIVE
        self.save()

    def complete(self):
        self.status = Project.STATUS_ATTIC
        self.save()

    def ignore(self):
        self.status = Project.STATUS_IGNORED
        self.save()


class Variable(models.Model):
    project = models.ForeignKey(Project, related_name='variables', null=True, blank=True)
    task_name = models.CharField(max_length=100, db_index=True)
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=2043)

    class Meta:
        ordering = ('task_name', 'key')


class Change(models.Model):
    CHANGE_TYPE_PULL_REQUEST = 10
    CHANGE_TYPE_PUSH = 20
    CHANGE_TYPE_CHOICES = [
        (CHANGE_TYPE_PULL_REQUEST, 'Pull Request'),
        (CHANGE_TYPE_PUSH, 'Push'),
    ]

    STATUS_NEW = Project.STATUS_NEW
    STATUS_ACTIVE = Project.STATUS_ACTIVE
    STATUS_ATTIC = Project.STATUS_ATTIC
    STATUS_IGNORED = Project.STATUS_IGNORED

    STATUS_CHOICES = Project.STATUS_CHOICES

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
        ordering = ('project__repository__name', '-updated')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('projects:change', kwargs={
                    'owner': self.project.repository.owner.login,
                    'repo_name': self.project.repository.name,
                    'change_pk': str(self.pk),
                })

    def get_status_url(self):
        return reverse('projects:change-status', kwargs={
                    'owner': self.project.repository.owner.login,
                    'repo_name': self.project.repository.name,
                    'change_pk': str(self.pk),
                })

    @property
    def title(self):
        if self.pull_request:
            return 'PR #%s' % self.pull_request.number
        else:
            return "%s:%s" % (self.push.commit.branch_name, self.push.commit.display_sha)

    @property
    def description(self):
        if self.pull_request:
            return self.pull_request.title
        else:
            return self.push.commit.title

    @property
    def user(self):
        if self.pull_request:
            return self.pull_request.user
        else:
            return self.push.commit.user

    @property
    def html_url(self):
        if self.pull_request:
            return self.pull_request.html_url
        else:
            return self.push.commit.url

    @property
    def is_complete(self):
        return self.status in (Change.STATUS_ATTIC, Change.STATUS_IGNORED)

    @property
    def is_pull_request(self):
        return self.change_type == Change.CHANGE_TYPE_PULL_REQUEST

    @property
    def is_push(self):
        return self.change_type == Change.CHANGE_TYPE_PUSH

    def approve(self):
        self.status = Change.STATUS_ACTIVE
        self.save()

    def complete(self):
        self.status = Change.STATUS_ATTIC
        self.completed = timezone.now()
        self.save()

        for build in self.builds.started():
            build.stop()

    def ignore(self):
        self.status = Change.STATUS_IGNORED
        self.save()


class BuildQuerySet(models.QuerySet):
    def started(self):
        return self.filter(status__in=(
                    Build.STATUS_CREATED,
                    Build.STATUS_RUNNING)
                )

    def running(self):
        return self.filter(status=Build.STATUS_RUNNING)

    def done(self):
        return self.filter(status=Build.STATUS_DONE)

    def finished(self):
        return self.filter(status__in=(
                Build.STATUS_DONE,
                Build.STATUS_ERROR,
                Build.STATUS_STOPPED
            ))


class Build(models.Model):
    STATUS_CREATED = 10
    STATUS_PENDING = 19
    STATUS_RUNNING = 20
    STATUS_DONE = 100
    STATUS_ERROR = 200
    STATUS_STOPPING = 9998
    STATUS_STOPPED = 9999

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        # No PENDING state for builds.
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
        (STATUS_STOPPING, 'Stopping'),
        (STATUS_STOPPED, 'Stopped'),
    ]

    RESULT_PENDING = 0
    RESULT_FAIL = 10
    RESULT_NON_CRITICAL_FAIL = 19
    RESULT_PASS = 20
    RESULT_CHOICES = [
        (RESULT_PENDING, 'Pending'),
        (RESULT_FAIL, 'Fail'),
        (RESULT_NON_CRITICAL_FAIL, 'Non-critical Fail'),
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

    error = models.TextField(blank=True)

    class Meta:
        ordering = ('-updated',)

    def __str__(self):
        return self.display_pk

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Bump the updated timestamp on the change
        self.change.save()

    def get_absolute_url(self):
        return reverse('projects:build', kwargs={
                    'owner': self.change.project.repository.owner.login,
                    'repo_name': self.change.project.repository.name,
                    'change_pk': str(self.change.pk),
                    'build_pk': str(self.pk)
                })

    def get_status_url(self):
        return reverse('projects:build-status', kwargs={
                    'owner': self.change.project.repository.owner.login,
                    'repo_name': self.change.project.repository.name,
                    'change_pk': str(self.change.pk),
                    'build_pk': str(self.pk)
                })

    def get_code_url(self):
        return reverse('projects:build-code', kwargs={
                    'owner': self.change.project.repository.owner.login,
                    'repo_name': self.change.project.repository.name,
                    'change_pk': str(self.change.pk),
                    'build_pk': str(self.pk)
                })
    @property
    def display_pk(self):
        return self.id.hex[:8]

    @property
    def has_started(self):
        return self.status in (
            Build.STATUS_CREATED,
            Build.STATUS_RUNNING
        )

    @property
    def is_finished(self):
        return self.status in (
            Build.STATUS_DONE,
            Build.STATUS_ERROR,
            Build.STATUS_STOPPED
        )

    @property
    def is_error(self):
        return self.status == Build.STATUS_ERROR

    @property
    def previous_success(self):
        try:
            # This relies on a bit of a trick. If this is a PUSH, then
            # pull_request is null - which means that this will find
            # the last passing Push build on this project.
            # However, if it *is* a PULL REQUEST, then it will find
            # the most recent successful build on that change.
            return Build.objects.filter(
                        change__project=self.change.project,
                        change__pull_request=self.pull_request,
                        status=Build.STATUS_DONE,
                        result=Build.RESULT_PASS,
                        created__lte=self.created
                    ).latest('completed')
        except Build.DoesNotExist:
            return None

    def full_status_display(self):
        if self.status == Build.STATUS_ERROR:
            return "Error: %s" % self.error
        else:
            return self.get_status_display()

    def start(self):
        start_build.send(sender=Build, build=self)

    def restart(self):
        if self.is_finished:
            self.tasks.all().delete()
            self.status = Build.STATUS_CREATED
            self.result = Build.RESULT_PENDING
            self.error = ''
            self.save()
            self.start()

    def resume(self):
        if self.is_error:
            self.status = Build.STATUS_RUNNING
            self.result = Build.RESULT_PENDING
            self.error = ''
            self.save()
            self.start()

    def stop(self):
        # If the build has not been started yet, mark it as stopped. If the
        # build has been started, mark the build as stopping. This will be
        # picked up on the next iteration of the build check, terminating any
        # tasks that are underway.
        if self.status == Build.STATUS_CREATED:
            self.status = Build.STATUS_STOPPED
            self.save()
        elif self.status == Build.STATUS_RUNNING:
            self.status = Build.STATUS_STOPPING
            self.save()
