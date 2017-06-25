from django.dispatch import Signal

new_build = Signal(providing_args=["pull_request"])
