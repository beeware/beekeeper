from github.models import PullRequest

from .models import Project, Change, Build


def new_project(sender, instance, created, *args, **kwargs):
    # When a github repository is saved, make sure there is
    # a project. Create one if it doesn't exist.
    try:
        Project.objects.get(repository=instance)
    except Project.DoesNotExist:
        Project.objects.create(repository=instance)


def new_push_build(sender, push=None, *args, **kwargs):
    """Create a new build in response to a push."""
    try:
        project = Project.objects.get(repository=push.commit.repository)
        if project.status == Project.STATUS_ACTIVE:

            # Stop all push builds on the same branch of this project
            for change in project.pushes.active(
                                ).filter(
                                    push__commit__branch_name=push.commit.branch_name
                                ):
                change.complete()

            # Find (or create) a change relating to this pull.
            try:
                change = Change.objects.get(
                        project=project,
                        change_type=Change.CHANGE_TYPE_PUSH,
                        pull_request=None,
                        push=push
                    )
            except Change.DoesNotExist:
                change = Change.objects.create(
                        project=project,
                        change_type=Change.CHANGE_TYPE_PUSH,
                        pull_request=None,
                        push=push,
                    )

            # Create a new build.
            build = Build.objects.create(change=change, commit=push.commit)
            build.start()

    except Project.DoesNotExist:
        pass


def new_pull_request_build(sender, update=None, *args, **kwargs):
    """Create a new build in response to a pull request update."""
    try:
        project = Project.objects.get(repository=update.pull_request.repository)
        if project.status == Project.STATUS_ACTIVE:
            # Find (or create) a change relating to this pull request.
            try:
                change = Change.objects.get(
                        project=project,
                        change_type=Change.CHANGE_TYPE_PULL_REQUEST,
                        pull_request=update.pull_request,
                        push=None,
                    )
            except Change.DoesNotExist:
                change = Change.objects.create(
                        project=project,
                        change_type=Change.CHANGE_TYPE_PULL_REQUEST,
                        pull_request=update.pull_request,
                        push=None,
                    )

            # Stop all pending builds on this change.
            for build in change.builds.pending():
                build.stop()

            # Create a new build.
            build = Build.objects.create(change=change, commit=update.commit)
            build.start()

    except Project.DoesNotExist:
        pass
