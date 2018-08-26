import os
import subprocess

import yaml

from beekeeper.config import load_task_configs


def run_task(name, phase, image, project_dir, is_critical, environment, **extra):
    print()
    print("---------------------------------------------------------------------------")
    print("{phase}: {name}".format(phase=phase, name=name))
    print("---------------------------------------------------------------------------")
    env_args = ' '.join(
        '-e {var}="{value}"'.format(var=var, value=value)
        for var, value in environment.items()
    )
    result = subprocess.run(
        'docker run -v {project_dir}:/app {env_args} {image}'.format(
            env_args=env_args,
            project_dir=project_dir,
            image=image
        ),
        shell=True,
        cwd=project_dir,
    )

    print("---------------------------------------------------------------------------")
    if result.returncode == 0:
        print("PASS: {name}".format(name=name))
        return True
    elif not is_critical:
        print("FAIL (non critical): {name}".format(name=name))
        return True
    else:
        print("FAIL: {name}".format(name=name))
        return False


def run_project(project_dir, action='pull_request'):
    with open(os.path.join(project_dir, 'beekeeper.yml')) as config_file:
        config = yaml.load(config_file.read())

    tasks = load_task_configs(config[action])

    phase = None
    successes = []
    failures = []
    for task in tasks:
        if task['phase'] != phase:
            if failures:
                break
            phase = task['phase']
            print("***** PHASE {phase} *************************************************************".format(**task))

        task['environment'].update({
            'TASK': task['slug'].split(':')[-1],
        })

        success = run_task(project_dir=project_dir, **task)

        if success:
            successes.append({
                'phase': task['phase'],
                'name': task['name'],
                'is_critical': task['is_critical']
            })
        else:
            failures.append({
                'phase': task['phase'],
                'name': task['name'],
                'is_critical': task['is_critical']
            })

    print()
    print("*************************************************************************".format(**task))
    if failures:
        print(f"BeeKeeper suite failed in phase {phase}:")
        for result in failures:
            print(f"    * {result['name']}")
    else:
        print("BeeKeeper suite passed.")
