from .models import Project, Build


def new_project(sender, instance, created, *args, **kwargs):
    # When a github repository is saved, make sure there is
    # a project. Create one if it doesn't exist.
    try:
        Project.objects.get(repository=instance)
    except Project.DoesNotExist:
        Project.objects.create(repository=instance)


def new_build(sender, pull_request=None, commit=None, *args, **kwargs):
    try:
        if pull_request:
            project = Project.objects.get(repository=pull_request.repository)
            # If the project is active, cancel all pending
            # builds on this PR.
            if project.status == Project.STATUS_ACTIVE:
                for build in Build.objects.filter(
                            project=project,
                            pull_request=pull_request,
                        ).pending():
                    build.cancel()

                # Create a new build.
                Build.objects.create(
                    project=project,
                    pull_request=pull_request,
                )
        else:
            # If the project is active, create a new build.
            project = Project.objects.get(repository=commit.repository)
            if project.status == Project.STATUS_ACTIVE:
                Build.objects.create(
                    project=project,
                    commit=commit,
                )

    except Project.DoesNotExist:
        pass
