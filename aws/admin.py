from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from .models import Task, Profile, Instance


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['project', 'build_pk', 'name', 'phase', 'is_critical', 'descriptor', 'status', 'result']
    list_filter = ['status', 'result', 'is_critical']
    raw_id_fields = ['build',]

    def build_pk(self, task):
        return task.build.display_pk
    build_pk.short_description = 'Build'

    def project(self, task):
        return task.build.change.project
    project.short_description = 'Project'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'instance_type']



def terminate(modeladmin, request, queryset):
    for obj in queryset:
        try:
            obj.terminate()
            messages.info(request, 'Terminating %s' % obj)
        except Exception as e:
            messages.error(request, str(e))
terminate.short_description = "Terminate instance"


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ['profile', 'ec2_id', 'container_arn', 'created', 'active', 'preferred']
    list_filter = ['active', 'preferred']
    raw_id_fields = ['tasks']
    actions = [terminate]
