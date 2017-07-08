from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['project', 'build_pk', 'name', 'phase', 'descriptor', 'status', 'result']
    list_filter = ['status', 'result']
    raw_id_fields = ['build',]

    def build_pk(self, task):
        return task.build.display_pk
    build_pk.short_description = 'Build'

    def project(self, task):
        return task.build.change.project
    project.short_description = 'Project'
