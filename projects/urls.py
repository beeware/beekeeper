from django.conf.urls import url, include
from django.contrib import admin

from projects import views as projects


urlpatterns = [
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)$', projects.project, name='project'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})$', projects.change, name='change'),
    url(r'^(?P<owner>[-\w]+)/(?P<repo_name>[-\w]+)/(?P<change_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})/(?P<build_pk>[-\da-fA-F]{8}-[-\da-fA-F]{4}-4[-\da-fA-F]{3}-[-\da-fA-F]{4}-[-\da-fA-F]{12})$', projects.build, name='build'),
]
