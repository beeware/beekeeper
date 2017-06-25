from django.shortcuts import render
from django.http import Http404

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
            'project': project
        })


def build(request, owner, repo_name, build_id):
    try:
        project = Project.objects.get(
                        repository__owner__login=owner,
                        repository__name=repo_name,
                    )
    except Project.DoesNotExist:
        raise Http404

    try:
        build = Build.objects.get(project=project, build_id=build_id)
    except Build.DoesNotExist:
        raise Http404

    return render(request, 'projects/build.html', {
            'project': project,
            'build': build,
        })
