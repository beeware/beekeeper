from django.shortcuts import render
from django.http import Http404

from github.models import Commit, PullRequest
from .models import Project, Build


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


def pull_request(request, owner, repo_name, pr):
    try:
        project = Project.objects.get(
                        repository__owner__login=owner,
                        repository__name=repo_name,
                    )
    except Project.DoesNotExist:
        raise Http404

    try:
        pull_request = PullRequest.objects.get(
                        repository=project.repository,
                        number=pr
                    )
    except PullRequest.DoesNotExist:
        raise Http404

    return render(request, 'projects/pull_request.html', {
            'project': project,
            'pull_request': pull_request,
        })


def build(request, owner, repo_name, build_pk, pr=None, sha=None):
    try:
        project = Project.objects.get(
                        repository__owner__login=owner,
                        repository__name=repo_name,
                    )
    except Project.DoesNotExist:
        raise Http404

    pull_request = None
    commit = None
    if pr:
        try:
            pull_request = PullRequest.objects.get(
                            repository=project.repository,
                            number=pr
                        )
        except PullRequest.DoesNotExist:
            raise Http404
    else:
        try:
            commit = Commit.objects.get(
                            repository=project.repository,
                            sha=sha
                        )
        except Commit.DoesNotExist:
            raise Http404

    try:
        build = Build.objects.get(
                    project=project,
                    pull_request=pull_request,
                    commit=commit,
                    pk=build_pk
                )
    except Build.DoesNotExist:
        raise Http404

    return render(request, 'projects/build.html', {
            'project': project,
            'pull_request': pull_request,
            'commit': commit,
            'build': build,
        })
