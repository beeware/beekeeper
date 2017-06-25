from .models import Project, Build


def new_project(sender, instance, created, *args, **kwargs):
    # When a github repository is saved, make sure there is
    # a project. Create one if it doesn't exist.
    try:
        Project.objects.get(repository=instance)
    except Project.DoesNotExist:
        Project.objects.create(repository=instance)



def new_build(sender, pull_request, *args, **kwargs):
    try:
        project = Project.objects.get(repository=pull_request.repository)

        # Cancel all existing pending builds on this PR.
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
    except Project.DoesNotExist:
        pass
