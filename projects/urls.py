from django.conf.urls import url, include
from django.contrib import admin

from projects import views as projects


urlpatterns = [
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)$', projects.project, name='project'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/(?P<build_id>[\d]+)$', projects.build, name='build'),
]
