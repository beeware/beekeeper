import json
import os
import time

from django.core.management.base import BaseCommand
from github import hooks as github_hooks


class Command(BaseCommand):
    help = 'Replay a directory of Github webhook data.'
    missing_args_message = (
        "No replay directory specified. Please provide the path of at least "
        "one replay directory in the command line."
    )

    def add_arguments(self, parser):
        parser.add_argument('args', metavar='fixture', nargs='+', help='Replay directories.')

    def handle(self, *fixture_labels, **options):
        self.verbosity = options['verbosity']

        self.replay(fixture_labels)

    def replay(self, fixture_labels):
        for label in fixture_labels:
            for filename in sorted(os.listdir(os.path.abspath(label))):
                try:
                    index, hook_type, description, filetype = filename.split('.')
                    if self.verbosity >= 1:
                        self.stdout.write(
                            "Replaying %s event: %s..." % (hook_type, description)
                        )

                    with open(os.path.join(os.path.abspath(label), filename)) as data:
                        payload = json.load(data)

                    github_hooks[hook_type](payload)
                    time.sleep(1)
                except ValueError:
                    self.stderr.write('Ignoring file %s' % filename)
                except KeyError:
                    if self.verbosity >= 1:
                        self.stdout.write(
                            "No handler for %s events" % hook_type
                        )
