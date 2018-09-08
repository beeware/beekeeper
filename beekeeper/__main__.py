from argparse import ArgumentParser
import os

from beekeeper import runner


def main():
    parser = ArgumentParser()
    parser.add_argument(
        '--action', '-a', dest='action', default='pull_request',
        choices=['pull_request', 'push', 'tag'],
        help='Specify the build action to run.',
    )
    parser.add_argument(
        '--slug', '-s', dest='slug',
        help='Specify the tasks to run (e.g., `beefore:pycodestyle` to run a specific task, '
             'or `beefore` to run all tasks in a phase.',
    )
    parser.add_argument(
        'project_dir', nargs='?', default='.',
        help='Directory containing a configured BeeKeeper project.'
    )
    options = parser.parse_args()

    runner.run_project(
        project_dir=os.path.abspath(options.project_dir),
        slug=options.slug,
        action=options.action,
    )


if __name__ == '__main__':
    main()
