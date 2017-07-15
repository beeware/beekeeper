import hashlib
import json

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.http import etag
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.utils import timezone

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


def etag_func(request, *args, **kwargs):
    return hashlib.sha256(str(timezone.now()).encode('utf-8')).hexdigest()


@never_cache
@etag(etag_func=etag_func)
def project_shield(request, owner, repo_name):
    try:
        project = Project.objects.get(
                        repository__owner__login=owner,
                        repository__name=repo_name,
                    )
    except Project.DoesNotExist:
        raise Http404

    build = project.current_build
    if build:
        if build.result == Build.RESULT_PASS:
            status = 'pass'
        elif build.result == Build.RESULT_FAIL:
            status = 'fail'
        elif build.result == Build.RESULT_NON_CRITICAL_FAIL:
            status = 'non_critical_fail'
        else:
            status = 'unknown'
    else:
        status = 'unknown'

    return render(request, 'projects/shields/%s.svg' % status, {},
        content_type='image/svg+xml;charset=utf-8'
    )


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
                        'label': build.commit.display_sha,
                        'title': build.commit.title,
                        'timestamp': build.created.strftime('%-d %b %Y, %H:%M'),
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
            'status': build.full_status_display(),
            'result': build.result,
            'tasks': {
                task.slug: {
                        'url': task.get_absolute_url(),
                        'name': task.name,
                        'phase': task.phase,
                        'status': task.full_status_display(),
                        'result': task.result,
                    }
                for task in build.tasks.all()
            },
            'finished': build.is_finished
        }), content_type="application/json")
