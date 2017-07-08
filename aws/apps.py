from django.apps import AppConfig


class AWSConfig(AppConfig):
    name = 'aws'
    verbose_name = 'Amazon Web Services ECS'

    def ready(self):
        from django.db.models import signals as django
        from projects import signals as projects
        from projects.models import Build
        from .handlers import start_build

        projects.start_build.connect(start_build, sender=Build)
