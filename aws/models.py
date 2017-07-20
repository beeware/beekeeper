import uuid

from github3.exceptions import GitHubError

from django.conf import settings
from django.contrib.postgres import fields as postgres
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from projects.models import Build, ProjectSetting


class TaskQuerySet(models.QuerySet):
    def started(self):
        return self.filter(status__in=(
                    Task.STATUS_PENDING,
                    Task.STATUS_RUNNING,
                ))

    def not_finished(self):
        return self.filter(status__in=(
                    Task.STATUS_PENDING,
                    Task.STATUS_RUNNING,
                    Task.STATUS_STOPPING,
                ))

    def pending(self):
        return self.filter(status=Task.STATUS_PENDING)

    def running(self):
        return self.filter(status=Task.STATUS_RUNNING)

    def stopping(self):
        return self.filter(status=Task.STATUS_STOPPING)

    def finished(self):
        return self.filter(status__in=[
                                Task.STATUS_DONE,
                                Task.STATUS_ERROR,
                                Task.STATUS_STOPPED,
                            ])

    def done(self):
        return self.filter(status=Task.STATUS_DONE)

    def error(self):
        return self.filter(status=Task.STATUS_ERROR)

    def failed(self):
        return self.filter(result=Build.RESULT_FAIL)


class Task(models.Model):
    STATUS_CREATED = Build.STATUS_CREATED
    STATUS_PENDING = Build.STATUS_PENDING
    STATUS_RUNNING = Build.STATUS_RUNNING
    STATUS_DONE = Build.STATUS_DONE
    STATUS_ERROR = Build.STATUS_ERROR
    STATUS_STOPPING = Build.STATUS_STOPPING
    STATUS_STOPPED = Build.STATUS_STOPPED

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
        (STATUS_STOPPING, 'Stopping'),
        (STATUS_STOPPED, 'Stopped'),
    ]
    objects = TaskQuerySet.as_manager()

    build = models.ForeignKey(Build, related_name='tasks')
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
    result = models.IntegerField(choices=Build.RESULT_CHOICES, default=Build.RESULT_PENDING)

    name = models.CharField(max_length=100, db_index=True)
    slug = models.CharField(max_length=100, db_index=True)

    phase = models.IntegerField()
    is_critical = models.BooleanField()
    started = models.DateTimeField(null=True, blank=True)
    pending = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    environment = postgres.JSONField()
    profile = models.CharField(max_length=100, null=True)
    descriptor = models.CharField(max_length=100)
    arn = models.CharField(max_length=100, null=True, blank=True)

    error = models.TextField(blank=True)

    class Meta:
        ordering = ('phase', 'name',)
        unique_together = [('build', 'slug')]

    def get_absolute_url(self):
        return reverse('projects:task', kwargs={
                    'owner': self.build.change.project.repository.owner.login,
                    'repo_name': self.build.change.project.repository.name,
                    'change_pk': str(self.build.change.pk),
                    'build_pk': str(self.build.pk),
                    'task_slug': self.slug
                })

    def get_status_url(self):
        return reverse('projects:task-status', kwargs={
                    'owner': self.build.change.project.repository.owner.login,
                    'repo_name': self.build.change.project.repository.name,
                    'change_pk': str(self.build.change.pk),
                    'build_pk': str(self.build.pk),
                    'task_slug': self.slug
                })

    def __str__(self):
        return self.name

    @property
    def has_started(self):
        return self.status in [
            Task.STATUS_RUNNING,
            Task.STATUS_DONE,
            Task.STATUS_ERROR,
        ]

    @property
    def is_finished(self):
        return self.status in (
            Task.STATUS_DONE,
            Task.STATUS_ERROR,
            Task.STATUS_STOPPED
        )

    @property
    def has_error(self):
        return self.status == Task.STATUS_ERROR

    @property
    def log_stream_name(self):
        return '%s/%s/%s' % (
            self.descriptor, self.descriptor, self.arn.rsplit('/', 1)[1]
        )

    def full_status_display(self):
        if self.status == Task.STATUS_ERROR:
            return "Error: %s" % self.error
        elif self.status == Task.STATUS_PENDING:
            return "Pending (for %s)" % timesince(self.pending)
        elif self.status == Task.STATUS_RUNNING:
            return "Running (for %s)" % timesince(self.started)
        else:
            return self.get_status_display()

    def start(self, ecs_client, ec2_client):
        if self.build.change.is_pull_request:
            pr_number = self.build.change.pull_request.number
        else:
            pr_number = ''

        environment = {
            'GITHUB_OWNER': self.build.commit.repository.owner.login,
            'GITHUB_PROJECT_NAME': self.build.commit.repository.name,
            'GITHUB_PR_NUMBER': pr_number,
            'CODE_URL': settings.BEEKEEPER_URL + self.build.get_code_url(),
            'SHA': self.build.commit.sha,
            'TASK': self.slug.split(':')[-1],
        }

        # Add environment variables from the project configuration.
        # Include, in order:
        #  * Global variables for all tasks
        #  * Global variables for a specific task
        #  * Project variables for all tasks
        #  * Project variables for a specific task
        for project in [None, self.build.change.project]:
            for descriptor in ['*', self.descriptor]:
                for var in ProjectSetting.objects.filter(project=project, descriptor=descriptor):
                    environment[var.key] = var.value

        # Add environment variables from the task configuration
        environment.update(self.environment)

        container_definition = {
            'name': self.descriptor,
            'environment': [
                {
                    'name': str(key),
                    'value': str(value)
                }
                for key, value in environment.items()
            ],
        }

        profile_name = self.profile if self.profile else 'default'
        try:
            profile = Profile.objects.get(slug=profile_name)
            container_definition.update({
                'cpu': profile.cpu,
                'memory': profile.memory
            })
        except Profile.DoesNotExist:
            raise RuntimeError("Unable to find a '%s' profile - is it defined?" % profile_name)

        response = ecs_client.run_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            taskDefinition=self.descriptor,
            overrides={
                'containerOverrides': [container_definition]
            }
        )
        if response['tasks']:
            self.arn = response['tasks'][0]['taskArn']
            self.status = Task.STATUS_PENDING
            self.pending = timezone.now()
            self.started = timezone.now()
            self.save()
        elif response['failures'][0]['reason'] in ['RESOURCE:CPU']:
            if self.status == Task.STATUS_CREATED:
                print("Spawning new %s instance..." % profile)
                instance = profile.start_instance(
                    key_name=settings.AWS_EC2_KEY_PAIR_NAME,
                    security_groups=settings.AWS_ECS_SECURITY_GROUP_IDS.split(':'),
                    subnet=settings.AWS_ECS_SUBNET_ID,
                    cluster_name=settings.AWS_ECS_CLUSTER_NAME,
                    ec2_client=ec2_client,
                )
                print("Created instance %s" % instance)
                self.status = Task.STATUS_PENDING
                self.pending = timezone.now()
                self.save()
        else:
            raise RuntimeError('Unable to start worker: %s' % response['failures'][0]['reason'])

    def stop(self, ecs_client):
        response = ecs_client.stop_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            task=self.arn
        )
        self.status = Task.STATUS_STOPPING
        self.save()

    def report(self, gh_repo):
        """Report the status of this task to GitHub

        gh_repo: An active GitHub API session.
        """
        gh_commit = gh_repo.commit(self.build.commit.sha)
        url = gh_commit._api.replace('commits', 'statuses')
        payload = {
            'context': '%s:%s/%s' % (settings.BEEKEEPER_NAMESPACE, self.phase, self.slug),
            'state': {
                Build.RESULT_PENDING: 'pending',
                Build.RESULT_FAIL: 'failure',
                Build.RESULT_NON_CRITICAL_FAIL: 'success',
                Build.RESULT_PASS: 'success',
            }[self.result],
            'target_url': settings.BEEKEEPER_URL + self.get_absolute_url(),
            'description': {
                Build.RESULT_PENDING: '%s pending...' % self.name,
                Build.RESULT_FAIL: '%s failed! Click for details.' % self.name,
                Build.RESULT_NON_CRITICAL_FAIL: '%s: non-critical problem found. Click for details.' % self.name,
                Build.RESULT_PASS: '%s passed.' % self.name,
            }[self.result],
        }
        response = gh_commit._post(url, payload)
        if not response.ok:
            raise GitHubError(response.reason)


class Profile(models.Model):
    EC2_TYPES = [
        {'name': 't2.nano',     'vcpu': 1,  'ecu': None,  'mem': 0.5,   'price': 0.0059},
        {'name': 't2.micro',    'vcpu': 1,  'ecu': None,  'mem': 1,     'price': 0.012},
        {'name': 't2.small',    'vcpu': 1,  'ecu': None,  'mem': 2,     'price': 0.023},
        {'name': 't2.medium',   'vcpu': 2,  'ecu': None,  'mem': 4,     'price': 0.047},
        {'name': 't2.large',    'vcpu': 2,  'ecu': None,  'mem': 8,     'price': 0.094},
        {'name': 't2.xlarge',   'vcpu': 4,  'ecu': None,  'mem': 16,    'price': 0.188},
        {'name': 't2.2xlarge',  'vcpu': 8,  'ecu': None,  'mem': 32,    'price': 0.376},
        {'name': 'm4.large',    'vcpu': 2,  'ecu': 6.5,   'mem': 8,     'price': 0.1},
        {'name': 'm4.xlarge',   'vcpu': 4,  'ecu': 13,    'mem': 16,    'price': 0.2},
        {'name': 'm4.2xlarge',  'vcpu': 8,  'ecu': 26,    'mem': 32,    'price': 0.4},
        {'name': 'm4.4xlarge',  'vcpu': 16, 'ecu': 53.5,  'mem': 64,    'price': 0.8},
        {'name': 'm4.10xlarge', 'vcpu': 40, 'ecu': 124.5, 'mem': 160,   'price': 2.0},
        {'name': 'm4.16xlarge', 'vcpu': 64, 'ecu': 188,   'mem': 256,   'price': 3.2},
        {'name': 'c4.large',    'vcpu': 2,  'ecu': 8,     'mem': 3.75,  'price': 0.1},
        {'name': 'c4.xlarge',   'vcpu': 4,  'ecu': 16,    'mem': 7.5,   'price': 0.199},
        {'name': 'c4.2xlarge',  'vcpu': 8,  'ecu': 31,    'mem': 15,    'price': 0.398},
        {'name': 'c4.4xlarge',  'vcpu': 16, 'ecu': 62,    'mem': 30,    'price': 0.796},
        {'name': 'c4.8xlarge',  'vcpu': 36, 'ecu': 132,   'mem': 60,    'price': 1.591},
        {'name': 'p2.xlarge',   'vcpu': 4,  'ecu': 12,    'mem': 61,    'price': 0.9},
        {'name': 'p2.8xlarge',  'vcpu': 32, 'ecu': 94,    'mem': 488,   'price': 7.2},
        {'name': 'p2.16xlarge', 'vcpu': 64, 'ecu': 188,   'mem': 732,   'price': 14.4},
        {'name': 'g3.4xlarge',  'vcpu': 16, 'ecu': 47,    'mem': 122,   'price': 1.14},
        {'name': 'g3.8xlarge',  'vcpu': 32, 'ecu': 94,    'mem': 244,   'price': 2.28},
        {'name': 'g3.16xlarge', 'vcpu': 64, 'ecu': 188,   'mem': 488,   'price': 4.56},
        {'name': 'r4.large',    'vcpu': 2,  'ecu': 7,     'mem': 15.25, 'price': 0.133},
        {'name': 'r4.xlarge',   'vcpu': 4,  'ecu': 13.5,  'mem': 30.5,  'price': 0.266},
        {'name': 'r4.2xlarge',  'vcpu': 8,  'ecu': 27,    'mem': 61,    'price': 0.532},
        {'name': 'r4.4xlarge',  'vcpu': 16, 'ecu': 53,    'mem': 122,   'price': 1.064},
        {'name': 'r4.8xlarge',  'vcpu': 32, 'ecu': 99,    'mem': 244,   'price': 2.128},
        {'name': 'r4.16xlarge', 'vcpu': 64, 'ecu': 195,   'mem': 488,   'price': 4.256},
    ]

    INSTANCE_TYPE_CHOICES = [
        (ec2['name'], ec2['name'])
        for ec2 in EC2_TYPES
    ]

    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, db_index=True)

    instance_type = models.CharField(max_length=20, choices=INSTANCE_TYPE_CHOICES)
    cpu = models.IntegerField(default=0)
    memory = models.IntegerField(default=0)
    ami = models.CharField(max_length=100, default='ami-57d9cd2e')

    idle = models.IntegerField(default=60)

    class Meta:
        ordering = ('slug',)

    def __str__(self):
        return self.name

    def start_instance(self, key_name, security_groups, subnet, cluster_name, aws_session=None, ec2_client=None):
        if ec2_client is None:
            if aws_session is None:
                aws_session = boto3.session.Session(
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )

            ec2_client = aws_session.client('ec2')

        response = ec2_client.run_instances(
            ImageId=self.ami,
            InstanceType=self.instance_type,
            MinCount=1,
            MaxCount=1,
            KeyName=key_name,
            SecurityGroupIds=security_groups,
            SubnetId=subnet,
            IamInstanceProfile={
                "Name": "ecsInstanceRole"
            },
            UserData="#!/bin/bash \n echo ECS_CLUSTER=%s >> /etc/ecs/ecs.config" % cluster_name
        )

        return response['Instances'][0]['InstanceId']
