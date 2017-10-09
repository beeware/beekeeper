import json

import boto3

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

from projects.models import Build

from .models import Task


def task(request, owner, repo_name, change_pk, build_pk, task_slug):
    try:
        task = Task.objects.get(
                        build__change__project__repository__owner__login=owner,
                        build__change__project__repository__name=repo_name,
                        build__change__pk=change_pk,
                        build__pk=build_pk,
                        slug=task_slug
                    )
    except Task.DoesNotExist:
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
    except Task.DoesNotExist:
        raise Http404

    try:
        kwargs = {
            'nextToken': request.GET['nextToken']
        }
    except KeyError:
        kwargs = {}

    aws_session = boto3.session.Session(
        region_name=settings.AWS_REGION,
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
        if task.has_error:
            log_data = None
            message = 'No logs; task did not start.'
            next_token = ''
            no_more_logs = True
        else:
            log_data = None
            message = 'Waiting for logs to become available...'
            next_token = ''
            no_more_logs = False

    return HttpResponse(json.dumps({
            'started': task.has_started,
            'log': log_data,
            'message': message,
            'status': task.full_status_display(),
            'result': task.result,
            'nextToken': next_token,
            'finished': task.is_finished and no_more_logs,
        }), content_type="application/json")


def current_tasks(request):
    return render(request, 'aws/current_tasks.html', {
        'pending': Task.objects.created().filter(build__status__in=(
                        Build.STATUS_CREATED,
                        Build.STATUS_RUNNING)
                    ).order_by('-updated'),
        'started': Task.objects.not_finished().filter(build__status__in=(
                        Build.STATUS_CREATED,
                        Build.STATUS_RUNNING)
                    ).order_by('-updated'),
        'recents': Task.objects.recently_finished().order_by('-updated'),
    })
