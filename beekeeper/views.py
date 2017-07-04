from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from projects.models import Project


def home(request):
    if request.method == "POST" and request.user.is_superuser:
        pks = [int(pk) for pk in request.POST.getlist('projects')]
        projects = Project.objects.filter(pk__in=pks)
        if 'approve' in request.POST:
            for project in projects:
                project.approve()
        elif 'ignore' in request.POST:
            for project in projects:
                project.ignore()

        return redirect('home')

    return render(request, 'home.html', {
            'projects': Project.objects.active(),
            'new_projects': Project.objects.pending_approval()
        })
