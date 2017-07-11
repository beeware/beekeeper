from django.conf import settings
from django.db import models
from django.utils import timezone


class User(models.Model):
    USER_TYPE_USER = 10
    USER_TYPE_ORGANIZATION = 20
    USER_TYPE_CHOICES = [
        (USER_TYPE_USER, "User"),
        (USER_TYPE_ORGANIZATION, "Organization"),
    ]
    USER_TYPE_VALUES = {
        "User": USER_TYPE_USER,
        "Organization": USER_TYPE_ORGANIZATION,
    }

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='github_user')
    github_id = models.IntegerField(db_index=True)
    login = models.CharField(max_length=100, db_index=True)
    avatar_url = models.URLField()
    html_url = models.URLField()
    user_type = models.IntegerField(choices=USER_TYPE_CHOICES, default=USER_TYPE_USER)

    class Meta:
        ordering = ('login',)

    def __str__(self):
        return "@%s" % self.login


class Repository(models.Model):
    owner = models.ForeignKey(User, related_name='repositories')
    name = models.CharField(max_length=100, db_index=True)
    github_id = models.IntegerField(db_index=True)

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    html_url = models.URLField()
    description = models.CharField(max_length=500)

    master_branch_name = models.CharField(max_length=100, default="master")

    class Meta:
        verbose_name_plural = 'repositories'
        ordering = ('name',)

    def __str__(self):
        return "github:%s" % self.full_name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Create a master branch if there are no branches.
        if not self.branches.exists():
            self.branches.create(name='master')

    @property
    def full_name(self):
        return '%s/%s' % (self.owner.login, self.name)

    @property
    def active_branch_names(self):
        return set(self.branches.filter(active=True).values_list('name', flat=True))


class Branch(models.Model):
    repository = models.ForeignKey(Repository, related_name='branches')
    name = models.CharField(max_length=100)

    active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'branches'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Commit(models.Model):
    repository = models.ForeignKey(Repository, related_name='commits')
    branch_name = models.CharField(max_length=100, db_index=True)
    sha = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(User, related_name='commits')

    created = models.DateTimeField()

    message = models.TextField()
    url = models.URLField()

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return "Commit %s on %s" % (self.sha, self.repository)

    @property
    def display_sha(self):
        return self.sha[:8]

    @property
    def title(self):
        return self.message.split('\n', 1)[0]


class PullRequestQuerySet(models.QuerySet):
    def open(self):
        return self.filter(state=PullRequest.STATE_OPEN)

    def closed(self):
        return self.filter(state=PullRequest.STATE_CLOSED)


class PullRequest(models.Model):
    STATE_OPEN = 10
    STATE_CLOSED = 100
    STATE_CHOICES = [
        (STATE_OPEN, 'Open'),
        (STATE_CLOSED, 'Closed'),
    ]
    STATE_VALUES = {
        'open': STATE_OPEN,
        'closed': STATE_CLOSED,
    }

    objects = PullRequestQuerySet.as_manager()

    repository = models.ForeignKey(Repository, related_name='pull_requests')
    number = models.IntegerField(db_index=True)
    github_id = models.IntegerField(db_index=True)

    created = models.DateTimeField()
    updated = models.DateTimeField()

    user = models.ForeignKey(User, related_name='pull_requests')
    title = models.CharField(max_length=100)
    html_url = models.URLField()
    diff_url = models.URLField()
    patch_url = models.URLField()
    state = models.IntegerField(choices=STATE_CHOICES, default=STATE_OPEN)

    class Meta:
        ordering = ('repository__name', 'number',)

    def __str__(self):
        return "PR %s on %s" % (self.number, self.repository)


class PullRequestUpdate(models.Model):
    pull_request = models.ForeignKey(PullRequest, related_name='updates')
    commit = models.ForeignKey(Commit, related_name='pull_request_updates')

    created = models.DateTimeField()

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return "Update %s to PR %s on %s" % (
            self.commit.sha, self.pull_request.number, self.pull_request.repository
        )


class Push(models.Model):
    commit = models.ForeignKey(Commit, related_name='pushes')

    created = models.DateTimeField()

    class Meta:
        verbose_name_plural = 'pushes'
        ordering = ('created',)

    def __str__(self):
        return "Push %s to branch %s on %s" % (
            self.commit.sha, self.commit.branch_name, self.commit.repository
        )
