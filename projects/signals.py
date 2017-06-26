from github.models import PullRequest

from .models import Project, Build


def new_project(sender, instance, created, *args, **kwargs):
    # When a github repository is saved, make sure there is
    # a project. Create one if it doesn't exist.
    try:
        Project.objects.get(repository=instance)
    except Project.DoesNotExist:
        Project.objects.create(repository=instance)


def new_build(sender, instance=None, *args, **kwargs):
    try:
        project = Project.objects.get(repository=instance.repository)
        if sender == PullRequest:
            # If the project is active, cancel all pending
            # builds on this PR.
            if project.status == Project.STATUS_ACTIVE:
                for build in Build.objects.filter(
                            project=project,
                            pull_request=instance,
                        ).pending():
                    build.cancel()

                # Create a new build.
                Build.objects.create(
                    project=project,
                    pull_request=instance,
                    commit=instance.commit,
                )
        else:
            # If the project is active, cancel all pending
            # mainline builds.
            project = Project.objects.get(repository=instance.repository)
            if project.status == Project.STATUS_ACTIVE:
                for build in Build.objects.filter(
                            project=project,
                            pull_request=None,
                        ).pending():
                    build.cancel()

                Build.objects.create(
                    project=project,
                    commit=instance,
                )

    except Project.DoesNotExist:
        pass
