from django.conf.urls import url, include
from django.contrib import admin

from github import views as github


urlpatterns = [
    url(r'^notify$', github.webhook, name='webhook'),
]
