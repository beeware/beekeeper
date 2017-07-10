from django.apps import apps
from django.conf import settings
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


def restart_build(modeladmin, request, queryset):
    for obj in queryset:
        obj.restart()
        messages.info(request, 'Restarting build %s' % obj)
restart_build.short_description = "Restart build"


def resume_build(modeladmin, request, queryset):
    for obj in queryset:
        obj.resume()
        messages.info(request, 'Resuming build %s' % obj)
resume_build.short_description = "Resume build"


class TaskInline(admin.TabularInline):
    model = apps.get_model(settings.BEEKEEPER_BUILD_APP, 'Task')
    fields = ['name', 'phase', 'status', 'result']
    extra = 0


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ['display_pk', 'project', 'change', 'commit_sha', 'user_with_avatar', 'status', 'result']
    list_filter = ['change__change_type', 'status']
    raw_id_fields = ['commit', 'change']
    actions = [restart_build, resume_build]
    inlines = [TaskInline]

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
