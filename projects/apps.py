from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    name = 'projects'

    def ready(self):
        from django.db.models import signals as django
        from github import signals as github
        from github.models import Repository, Commit, PullRequest
        from .signals import new_project, new_build

        django.post_save.connect(new_project, sender=Repository)

        github.new_build.connect(new_build, sender=Commit)
        github.new_build.connect(new_build, sender=PullRequest)
