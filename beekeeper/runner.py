import os
import subprocess

import yaml

from beekeeper.config import load_task_configs


def run_task(name, phase, descriptor, project_dir, is_critical, environment, **extra):
    print()
    print("---------------------------------------------------------------------------")
    print(f"{phase}: {name}".format(phase=phase, name=name))
    print("---------------------------------------------------------------------------")
    result = subprocess.run(
        f'docker run -v {project_dir}:/app {descriptor}',
        shell=True,
        cwd=project_dir,
        env=environment
    )

    print("---------------------------------------------------------------------------")
    if result.returncode == 0:
        print(f"PASS: {name}")
        return True
    elif not is_critical:
        print(f"FAIL (non critical): {name}")
        return True
    else:
        print(f"FAIL: {name}")
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
            print(f"***** PHASE {phase} *************************************************************".format(**task))

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
