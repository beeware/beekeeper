import json

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

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


def change_status(request, owner, repo_name, change_pk):
    try:
        change = Change.objects.get(
                    project__repository__owner__login=owner,
                    project__repository__name=repo_name,
                    pk=change_pk
                )
    except Change.DoesNotExist:
        raise Http404

    return HttpResponse(json.dumps({
            'builds': {
                build.display_pk: {
                        'url': build.get_absolute_url(),
                        'label': build.display_pk,
                        'status': build.get_status_display(),
                        'result': build.result,
                    }
                for build in change.builds.all()
            },
            'complete': change.is_complete
        }), content_type="application/json")


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

    if request.method == "POST" and request.user.is_superuser:
        if 'resume' in request.POST:
            build.resume()
        elif 'restart' in request.POST:
            build.restart()

        return redirect(build.get_absolute_url())

    return render(request, 'projects/build.html', {
            'project': build.change.project,
            'change': build.change,
            'commit': build.commit,
            'build': build,
        })


def build_status(request, owner, repo_name, change_pk, build_pk):
    try:
        build = Build.objects.get(
                        change__project__repository__owner__login=owner,
                        change__project__repository__name=repo_name,
                        change__pk=change_pk,
                        pk=build_pk,
                    )
    except Build.DoesNotExist:
        raise Http404

    return HttpResponse(json.dumps({
            'status': build.get_status_display(),
            'error': build.error,
            'result': build.result,
            'tasks': {
                task.slug: {
                        'status': task.get_status_display(),
                        'result': task.result,
                    }
                for task in build.tasks.all()
            },
            'finished': build.is_finished
        }), content_type="application/json")
