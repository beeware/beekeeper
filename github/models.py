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

    class Meta:
        verbose_name_plural = 'repositories'

    def __str__(self):
        return "Github repository %s" % self.full_name

    @property
    def full_name(self):
        return '%s/%s' % (self.owner.login, self.name)



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

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, related_name='pull_requests')
    title = models.CharField(max_length=100)
    html_url = models.URLField()
    diff_url = models.URLField()
    patch_url = models.URLField()
    state = models.IntegerField(choices=STATE_CHOICES, default=STATE_OPEN)

    def __str__(self):
        return "PR %s on %s" % (self.number, self.repository)


