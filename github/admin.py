from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import User, Repository, Branch, Commit, PullRequest, PullRequestUpdate, Push


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['login', 'user_with_avatar']
    list_filter = ['user_type']
    raw_id_fields = ['user']

    def user_with_avatar(self, user):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            user.avatar_url, user, user
        ))
    user_with_avatar.short_description = 'User'


class BranchInline(admin.TabularInline):
    model = Branch
    fields = ['name', 'active']
    extra = 0


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ['user_with_avatar', 'name', 'description']
    raw_id_fields = ['owner',]
    inlines = [BranchInline]

    def user_with_avatar(self, repo):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            repo.owner.avatar_url, repo.owner, repo.owner
        ))
    user_with_avatar.short_description = 'Owner'


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ['sha', 'repository', 'user_with_avatar', 'created']
    raw_id_fields = ['repository', 'user']
    date_heirarchy = 'created'

    def user_with_avatar(self, commit):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            commit.user.avatar_url, commit.user, commit.user
        ))
    user_with_avatar.short_description = 'User'


class PullRequestUpdateInline(admin.TabularInline):
    model = PullRequestUpdate
    list_display = ['created', 'user_with_avatar', 'commit']
    raw_id_fields = ['commit']
    extra = 0

    def user_with_avatar(self, pru):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            pru.commit.user.avatar_url, pru.commit.user, pru.commit.user
        ))
    user_with_avatar.short_description = 'User'


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ['number', 'repository', 'user_with_avatar', 'created', 'state']
    list_filter = ['state']
    date_heirarchy = 'created'
    raw_id_fields = ['repository', 'user']
    inlines = [PullRequestUpdateInline]

    def user_with_avatar(self, pr):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            pr.user.avatar_url, pr.user, pr.user
        ))
    user_with_avatar.short_description = 'User'


@admin.register(Push)
class PushAdmin(admin.ModelAdmin):
    list_display = ['commit', 'user_with_avatar', 'created']
    date_heirarchy = 'created'
    raw_id_fields = ['commit']

    def user_with_avatar(self, push):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            push.commit.user.avatar_url, push.commit.user, push.commit.user
        ))
    user_with_avatar.short_description = 'user'
