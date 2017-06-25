from django.contrib import admin

from .models import Project, Build


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['repository', 'status']
    list_filter = ['status']
    raw_id_fields = ['repository']


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ['project', 'pull_request', 'status']
    list_filter = ['status']
    raw_id_fields = ['project', 'pull_request']
