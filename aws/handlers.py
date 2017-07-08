from .tasks import check_build

def start_build(sender, build, *args, **kwargs):
    check_build.delay(str(build.pk))
