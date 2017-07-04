from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from .models import Project, Change, Build


def approve(modeladmin, request, queryset):
    for obj in queryset:
        obj.status = obj.approve()
        obj.save()
        messages.info(request, 'Approving %s for build' % obj)
approve.short_description = "Approve for build"


def attic(modeladmin, request, queryset):
    for obj in queryset:
        obj.status = obj.complete()
        obj.save()
        messages.info(request, 'Moving %s to the attic' % obj)
attic.short_description = "Move to attic"


def ignore(modeladmin, request, queryset):
    for obj in queryset:
        obj.status = obj.ignore()
        obj.save()
        messages.info(request, 'Ignoring %s' % obj)
ignore.short_description = "Ignore"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['repository', 'status']
    list_filter = ['status']
    raw_id_fields = ['repository']
    actions = [approve, attic, ignore]


class BuildInline(admin.TabularInline):
    model = Build
    list_display = ['created', 'commit', 'status', 'result']
    raw_id_fields = ['commit',]
    extra = 0


@admin.register(Change)
class ChangeAdmin(admin.ModelAdmin):
    list_display = ['project', 'title', 'status', 'completed']
    list_filter = ['change_type', 'status']
    raw_id_fields = ['project', 'pull_request', 'push']
    actions = [approve, attic, ignore]
    inlines = [BuildInline]

    def title(self, change):
        return change.title
    title.short_description = 'Title'


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ['display_pk', 'project', 'change', 'commit_sha', 'user_with_avatar', 'status', 'result']
    list_filter = ['change__change_type', 'status']
    raw_id_fields = ['commit', 'change']

    def display_pk(self, build):
        return build.display_pk
    display_pk.short_description = 'Build'

    def project(self, build):
        return build.change.project
    project.short_description = 'Project'

    def commit_sha(self, build):
        return build.commit.display_sha
    commit_sha.short_description = 'Commit'

    def user_with_avatar(self, build):
        return mark_safe('<img src="%s" style="width: 32px" alt="Github avatar for %s"> %s' % (
            build.commit.user.avatar_url, build.commit.user, build.commit.user
        ))
    user_with_avatar.short_description = 'user'
