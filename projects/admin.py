from django.contrib import admin

from .models import Project, Build

def approve(modeladmin, request, queryset):
    for project in queryset:
        project.status = Project.STATUS_ACTIVE
        messages.info(request, 'Approving %s for build' % project)
approve.short_description = "Approve for build"


def attic(modeladmin, request, queryset):
    for project in queryset:
        project.status = Project.STATUS_ATTIC
        messages.info(request, 'Moving %s to the attic' % project)
attic.short_description = "Move to attic"


def ignore(modeladmin, request, queryset):
    for project in queryset:
        project.status = Project.STATUS_IGNORE
        messages.info(request, 'Ignoring %s' % project)
ignore.short_description = "Ignore"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['repository', 'status']
    list_filter = ['status']
    raw_id_fields = ['repository']
    actions = [approve, attic, ignore]


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ['project', 'pull_request', 'status']
    list_filter = ['status']
    raw_id_fields = ['project', 'pull_request']
