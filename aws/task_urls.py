from django.conf.urls import url
from django.contrib import admin

from aws import views as aws


urlpatterns = [
    url(r'^(?P<task_slug>[-\w\._:]+)$', aws.task, name='task'),
    url(r'^(?P<task_slug>[-\w\._:]+)/status$', aws.task_status, name='task-status'),
]
