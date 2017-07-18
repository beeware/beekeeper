BeeKeeper
=========

Look after all the little worker bees.

Getting started
---------------

To deploy a new BeeKeeper instance, clone this repo, and then run::

    $ heroku create
    $ git push heroku master
    $ heroku addons:create heroku-postgresql:hobby-dev
    $ heroku addons:create heroku-redis:hobby-dev
    $ heroku config:set BEEKEEPER_URL=https://<your domain>
    $ heroku scale worker=1
    $ heroku run ./manage.py migrate
    $ heroku run ./manage.py createsuperuser

Django
~~~~~~

Configure a `SECRET_KEY` for the Django instance

    >>> from django.core.management.utils import get_random_secret_key
    >>> get_random_secret_key()
    'qn219x$#ox1$+(m4hdzi-q+5g&o9^7)(x5l8^y51+rrcvs*o3-'

Then set a `SECRET_KEY` configuration variable in your Heroku instance, and
put::

    SECRET_KEY=<your key here>

in the .env file inthe project home directory.

Github
~~~~~~

Next, go to the repository you want to manage, go to Settings, then Webhooks,
and add a new webhook for
`https:<your app name>.herokuapp.com/github/notify>`. When prompted for a secret,
generate one::

    >>> from django.utils.crypto import get_random_string
    >>> get_random_string(50)
    'nuiVypAArY7lFDgMdyC5kwutDGQdDc6rXljuIcI5iBttpPebui'

Once the webhook has been created, create a `GITHUB_WEBHOOK_KEY` Heroku
configuration variable to this string, and put::

    GITHUB_WEBHOOK_KEY=<your key here>

in the .env file in the project home directory.

Then, generate a `personal access token
<https://help.github.com/articles/creating-a-personal-access-token-for-the-
command-line/>`__, create `GITHUB_USERNAME` and `GITHUB_ACCESS_TOKEN` Heroku
configuration variables with that value, and put::

    GITHUB_USERNAME=<your github username>
    GITHUB_ACCESS_TOKEN=<your token here>

in the .env file in the project home directory.

Sendgrid
~~~~~~~~

Sign up for a Sendgrid account, then get an API key. Create a
`SENDGRID_API_KEY` configuration value on Heroku, and put::

    SENDGRID_API_KEY=<your key here>

In the .env file in the project home directory.

Amazon AWS
~~~~~~~~~~

Log into (or sign up for) your Amazon AWS account, and obtain an access key
and secret access key. Create the `AWS_ACCESS_KEY_ID`, `AWS_REGION` and
`AWS_SECRET_ACCESS_KEY` Heroku configuration variables, and put::

    AWS_ACCESS_KEY_ID=<your key here>
    AWS_REGION=<your AWS region>
    AWS_SECRET_ACCESS_KEY=<your secret key here>

In the .env file in the project home directory.

Go to the ECS panel and create an EC2 cluster in an AWS
region of your choice. If you create an "empty" cluster, BeeKeeper
will spin up new instances whenever build tasks are submitted. If you
create a non-empty cluster, those resources will be permanently
available for builds - but you'll also be paying for that availability.

Once you've created your cluster, set the `AWS_ECS_CLUSTER_NAME` Heroku
configuration variables, and put::

    AWS_ECS_AMI=<your prefered AWS image; 'ami-57d9cd2e' by default>
    AWS_ECS_CLUSTER_NAME=<your cluster name here>
    AWS_ECS_SUBNET_ID=<your ECS subnet>
    AWS_ECS_SECURITY_GROUP_IDS=<colon separate list of security key IDs>

In the .env file in the project home directory.

Docker images
~~~~~~~~~~~~~

Create a clone of the `pybee/comb <https://github.com/pybee/comb>`__

    $ pip install waggle
    $ waggle waggler
