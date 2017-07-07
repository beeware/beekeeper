#!/usr/bin/env python
import os
import subprocess

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        with open('.env') as envfile:
            for line in envfile:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass

    subprocess.run([
        'celery',
        '-A', 'config',
        'worker',
        '-c', '2',
        '--loglevel=INFO'
    ])
