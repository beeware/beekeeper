from django.conf.urls import url
from django.contrib import admin

from . import views as aws


urlpatterns = [
    url(r'^$', aws.current_tasks, name='current-tasks'),
]
