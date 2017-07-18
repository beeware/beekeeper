from django.conf import settings
from django.conf.urls import url, include
from django.contrib import admin

from projects import views as projects


urlpatterns = [
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)$',
        projects.project, name='project'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/shield$',
        projects.project_shield, name='project-shield'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})$',
        projects.change, name='change'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/status$',
        projects.change_status, name='change-status'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/build/(?P<build_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})$',
        projects.build, name='build'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/build/(?P<build_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/status$',
        projects.build_status, name='build-status'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/build/(?P<build_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/code$',
        projects.build_code, name='build-code'),

    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/change/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/build/(?P<build_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/task/',
        include('%s.urls' % settings.BEEKEEPER_BUILD_APP))
]
