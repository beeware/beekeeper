import json

import boto3

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

from github.models import Commit, PullRequest
from .models import Project, Change, Build, Task


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


def task(request, owner, repo_name, change_pk, build_pk, task_slug):
    try:
        task = Task.objects.get(
                        build__change__project__repository__owner__login=owner,
                        build__change__project__repository__name=repo_name,
                        build__change__pk=change_pk,
                        build__pk=build_pk,
                        slug=task_slug
                    )
    except Build.DoesNotExist:
        raise Http404

    return render(request, 'projects/task.html', {
            'project': task.build.change.project,
            'change': task.build.change,
            'commit': task.build.commit,
            'build': task.build,
            'task': task,
        })


def task_status(request, owner, repo_name, change_pk, build_pk, task_slug):
    try:
        task = Task.objects.get(
                        build__change__project__repository__owner__login=owner,
                        build__change__project__repository__name=repo_name,
                        build__change__pk=change_pk,
                        build__pk=build_pk,
                        slug=task_slug
                    )
    except Build.DoesNotExist:
        raise Http404

    try:
        kwargs = {
            'nextToken': request.GET['nextToken']
        }
    except KeyError:
        kwargs = {}

    aws_session = boto3.session.Session(
        region_name=settings.AWS_ECS_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    logs = aws_session.client('logs')

    try:
        log_response = logs.get_log_events(
            logGroupName='beekeeper',
            logStreamName=task.log_stream_name,
            **kwargs
        )
        log_data = '\n'.join(
                event['message']
                for event in log_response['events']
            )
        message = None
        next_token = log_response['nextForwardToken']
        no_more_logs = log_response['nextForwardToken'] == kwargs.get('nextToken', None)
    except Exception as e:
        log_data = None
        message = 'Waiting for logs to become available...'
        next_token = ''
        no_more_logs = False

    return HttpResponse(json.dumps({
            'started': task.has_started,
            'log': log_data,
            'message': message,
            'status': task.get_status_display(),
            'result': task.result,
            'nextToken': next_token,
            'finished': task.is_finished and no_more_logs,
        }), content_type="application/json")
