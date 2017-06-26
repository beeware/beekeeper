from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import User, Repository, Commit, PullRequest


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['login', 'avatar', 'user']
    list_filter = ['user_type']
    raw_id_fields = ['user']

    def avatar(self, user):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar">' % user.avatar_url)
    avatar.short_description = 'Avatar'


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ['owner', 'avatar', 'name', 'description']
    raw_id_fields = ['owner',]

    def avatar(self, repo):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar">' % repo.owner.avatar_url)
    avatar.short_description = 'Avatar'


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ['sha', 'repository', 'user', 'avatar']
    raw_id_fields = ['repository', 'user']

    def avatar(self, pr):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar">' % pr.user.avatar_url)
    avatar.short_description = 'Avatar'


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ['number', 'repository', 'user', 'avatar', 'state']
    list_filter = ['state']
    raw_id_fields = ['repository', 'user', 'merge_commit']

    def avatar(self, pr):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar">' % pr.user.avatar_url)
    avatar.short_description = 'Avatar'
