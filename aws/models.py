import base64
import uuid

import boto3
from botocore.exceptions import ClientError

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
                    Task.STATUS_WAITING,
                    Task.STATUS_RUNNING,
                ))

    def not_finished(self):
        return self.filter(status__in=(
                    Task.STATUS_WAITING,
                    Task.STATUS_RUNNING,
                    Task.STATUS_STOPPING,
                ))

    def waiting(self):
        return self.filter(status=Task.STATUS_WAITING)

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
    STATUS_WAITING = Build.STATUS_WAITING
    STATUS_RUNNING = Build.STATUS_RUNNING
    STATUS_DONE = Build.STATUS_DONE
    STATUS_ERROR = Build.STATUS_ERROR
    STATUS_STOPPING = Build.STATUS_STOPPING
    STATUS_STOPPED = Build.STATUS_STOPPED

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_WAITING, 'Waiting'),
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
    queued = models.DateTimeField(null=True, blank=True)
    started = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    environment = postgres.JSONField()
    profile_slug = models.CharField(max_length=100, default='default')
    descriptor = models.CharField(max_length=100)
    arn = models.CharField(max_length=100, null=True, blank=True)

    error = models.TextField(blank=True)

    class Meta:
        ordering = ('phase', 'name',)
        unique_together = [('build', 'slug')]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # If this task finishes, is stopped, or errors out,
        # start the timer on the sweeper to shut down the instance
        # used to run it.
        if self.is_finished:
            from .tasks import sweeper
            sweeper.apply_async((str(self.pk),), countdown=self.profile.cooldown)

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

    @property
    def profile(self):
        return Profile.objects.get(slug=self.profile_slug)

    def full_status_display(self):
        if self.status == Task.STATUS_ERROR:
            return "Error: %s" % self.error
        elif self.status == Task.STATUS_WAITING:
            return "Waiting (for %s)" % timesince(self.queued)
        elif self.status == Task.STATUS_RUNNING:
            return "Running (for %s)" % timesince(self.started)
        elif self.status == Task.STATUS_DONE:
            return "Done (Task took %s)" % timesince(self.started, now=self.completed)
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

        try:
            profile = self.profile
        except Profile.DoesNotExist:
            raise RuntimeError("Unable to find a '%s' profile - is it defined?" % profile_name)

        container_definition.update({
            'cpu': profile.cpu,
            'memory': profile.memory,
        })

        response = ecs_client.run_task(
            cluster=settings.AWS_ECS_CLUSTER_NAME,
            taskDefinition=self.descriptor,
            overrides={
                'containerOverrides': [container_definition]
            }
        )
        if response['tasks']:
            container_arn = response['tasks'][0]['containerInstanceArn']

            try:
                instance = Instance.objects.get(profile=profile, container_arn=container_arn)
                print("Task deployed on container %s." % container_arn)
            except Instance.DoesNotExist:
                print("Task deployed on container %s..." % container_arn)
                try:
                    ec2_id = ecs_client.describe_container_instances(
                            cluster=settings.AWS_ECS_CLUSTER_NAME,
                            containerInstances=[container_arn]
                        )['containerInstances'][0]['ec2InstanceId']
                    print("Container %s is on EC2 instance %s." % (container_arn, ec2_id))
                    instance = Instance.objects.get(profile=profile, ec2_id=ec2_id)
                    instance.container_arn = container_arn
                except Instance.DoesNotExist:
                    print("EC2 instance %s must be new. Recording instance." % ec2_id)
                    instance = Instance(profile=profile, ec2_id=ec2_id)

            instance.save()
            instance.tasks.add(self)

            # Add the timeout reaper task
            from .tasks import reaper
            reaper.apply_async((str(self.pk),), countdown=profile.timeout)

            self.arn = response['tasks'][0]['taskArn']
            self.status = Task.STATUS_WAITING
            if self.queued is None:
                self.queued = timezone.now()
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
                if instance:
                    print("Created instance %s" % instance)
                else:
                    print("Maximum number of %s instances reached. Waiting for spare capacity..." % profile)
                self.status = Task.STATUS_WAITING
                self.queued = timezone.now()
                self.save()
        else:
            print("FAILURE RESPONSE: %s" % response)
            raise RuntimeError('Unable to start worker: %s' % response['failures'][0]['reason'])

    def stop(self, aws_session=None, ecs_client=None):
        if ecs_client is None:
            if aws_session is None:
                aws_session = boto3.session.Session(
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )

            ecs_client = aws_session.client('ecs')

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
        # Price is us-west-2 price, as of 20 July 2017
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
    INSTANCE_TYPE_PRICES = {
        ec2['name']: str(ec2['price'])
        for ec2 in EC2_TYPES
    }

    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, db_index=True)

    instance_type = models.CharField(max_length=20, choices=INSTANCE_TYPE_CHOICES)
    spot = models.BooleanField(default=False)
    cpu = models.IntegerField(default=0)
    memory = models.IntegerField(default=0)
    ami = models.CharField('AMI', max_length=100, default='ami-57d9cd2e')

    timeout = models.IntegerField(default=60 * 60)
    cooldown = models.IntegerField(default=60)

    max_instances = models.IntegerField(null=True, blank=True)
    min_instances = models.IntegerField(default=0)

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

        if self.max_instances is None or self.instances.active().count() < self.max_instances:
            instance_data = {
                'ImageId': self.ami,
                'InstanceType': self.instance_type,
                'KeyName': key_name,
                'SecurityGroupIds': security_groups,
                'SubnetId': subnet,
                'IamInstanceProfile': {
                    "Name": "ecsInstanceRole"
                },
                'UserData': "#!/bin/bash \n echo ECS_CLUSTER=%s >> /etc/ecs/ecs.config" % cluster_name
            }

            if self.spot:
                # Spot instances need the user data to be base64 encoded.
                # Yay for API consistency!!
                instance_data['UserData'] = base64.b64encode(
                    instance_data['UserData'].encode('utf-8')
                ).decode('utf-8')
                response = ec2_client.request_spot_instances(
                    InstanceCount=1,
                    SpotPrice=Profile.INSTANCE_TYPE_PRICES[instance_data["InstanceType"]],
                    LaunchSpecification=instance_data
                )
                instance_id = response['SpotInstanceRequests'][0]['InstanceId']
            else:
                response = ec2_client.run_instances(
                    MinCount=1,
                    MaxCount=1,
                    **instance_data
                )
                instance_id = response['Instances'][0]['InstanceId']

            # Create a database record of the instance.
            instance = Instance.objects.create(profile=self, ec2_id=instance_id)
        else:
            instance = None

        return instance


class InstanceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active=True)


class Instance(models.Model):
    objects = InstanceQuerySet.as_manager()

    profile = models.ForeignKey(Profile, related_name='instances')
    container_arn = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    ec2_id = models.CharField(max_length=100, db_index=True)

    tasks = models.ManyToManyField(Task, related_name='instances', blank=True)

    created = models.DateTimeField(default=timezone.now)
    checked = models.DateTimeField(auto_now=True)
    terminated = models.DateTimeField(null=True, blank=True)

    active = models.BooleanField(default=True)

    def __str__(self):
        return 'Container %s (EC2 ID %s)' % (self.container_arn, self.ec2_id)

    def terminate(self, aws_session=None, ec2_client=None):
        if ec2_client is None:
            if aws_session is None:
                aws_session = boto3.session.Session(
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )

            ec2_client = aws_session.client('ec2')

        # Save the new state of the instance.
        self.active = False
        self.save()

        # Actually terminate the instance
        try:
            ec2_client.terminate_instances(InstanceIds=[self.ec2_id])

            # Record the termination time.
            self.terminated = timezone.now()
            self.save()
        except ClientError as e:
            raise RuntimeError('Problem terminating %s: [%s] %s' % (
                self, e.response['Error']['Code'], e.response['Error']['Message'],
            ))
