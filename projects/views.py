from django.shortcuts import render
from django.http import Http404

from github.models import Commit, PullRequest
from .models import Project, Change, Build


def project(request, owner, repo_name):
    try:
        project = Project.objects.get(
                        repository__owner__login=owner,
                        repository__name=repo_name,
                    )
    except Project.DoesNotExist:
        raise Http404

    return render(request, 'projects/project.html', {
            'project': project,
        })


def change(request, owner, repo_name, change_pk):
    try:
        change = Change.objects.get(
                    project__repository__owner__login=owner,
                    project__repository__name=repo_name,
                    pk=change_pk
                )
    except Change.DoesNotExist:
        raise Http404

    return render(request, 'projects/change.html', {
            'project': change.project,
            'change': change,
        })


def build(request, owner, repo_name, change_pk, build_pk):
    try:
        build = Build.objects.get(
                        change__project__repository__owner__login=owner,
                        change__project__repository__name=repo_name,
                        change__pk=change_pk,
                        pk=build_pk,
                    )
    except Build.DoesNotExist:
        raise Http404

    return render(request, 'projects/build.html', {
            'project': build.change.project,
            'change': build.change,
            'commit': build.commit,
            'build': build,
        })
