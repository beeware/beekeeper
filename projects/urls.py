from django.conf.urls import url, include
from django.contrib import admin

from projects import views as projects


urlpatterns = [
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)$', projects.project, name='project'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/pr/(?P<pr>[\d]+)$', projects.pull_request, name='pull_request'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/pr/(?P<pr>[\d]+)/build/(?P<build_pk>[\d]+)$', projects.build, name='build'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/commit/(?P<sha>\w{40})/build/(?P<build_pk>[\d]+)$', projects.build, name='build'),
]
