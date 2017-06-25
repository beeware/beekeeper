from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import User, Repository, PullRequest


def avatar(github_user):
    return mark_safe('<img src="%s" alt="Github avatar">' % github_user.avatar_url)
avatar.short_description = 'Avatar'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['login', avatar, 'user']
    list_filter = ['user_type']
    raw_id_fields = ['user']


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ['owner', 'name', 'description']
    raw_id_fields = ['owner',]


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ['number', 'repository', 'user', 'state']
    list_filter = ['state']
    raw_id_fields = ['repository', 'user']
