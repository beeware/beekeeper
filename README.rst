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

Configure a `SECRET_KEY` for the Django instance::

    >>> from django.core.management.utils import get_random_secret_key
    >>> get_random_secret_key()
    'qn219x$#ox1$+(m4hdzi-q+5g&o9^7)(x5l8^y51+rrcvs*o3-'

Then set a `SECRET_KEY` configuration variable in your Heroku instance, and
put::

    SECRET_KEY=<your key here>

in the .env file inthe project home directory.

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

Once you've created your cluster, set the `AWC_EC2_KEY_PAIR_NAME`,
`AWS_ECS_AMI`, `AWS_ECS_CLUSTER_NAME`, `AWS_ECS_SUBNET_ID` and
`AWS_ECS_SECURITY_GROUP_IDS` Heroku configuration variables, and put::

    AWS_EC2_KEY_PAIR_NAME=<your keypair name>
    AWS_ECS_AMI=<your prefered AWS image; 'ami-57d9cd2e' by default>
    AWS_ECS_CLUSTER_NAME=<your cluster name here>
    AWS_ECS_SUBNET_ID=<your ECS subnet>
    AWS_ECS_SECURITY_GROUP_IDS=<colon separate list of security key IDs>

In the .env file in the project home directory.

Docker images
~~~~~~~~~~~~~

Check out a Comb, (BeeWare uses `this one
<https://github.com/pybee/comb/tree/pybee>`__). Create a file named `.env` in
the root of that checkout, and create a file called `.env` that contains the
following content::

    AWS_REGION=<Your AWS region (e.g., us-west-2)>
    AWS_ACCESS_KEY_ID=<Your AWS access key>
    AWS_SECRET_ACCESS_KEY=<Your AWS secret access key>

Then waggle the tasks in the comb::

    $ pip install waggle
    $ waggle waggler

Profiles
~~~~~~~~

Log into the admin, and create an AWS profile with the slug of `default`. This
is the machine type that will run tests by default. A reasonable starting point
is:

* **Instance type:** `t2.micro`
* **CPU:** 0
* **Memory:** 200

The value for CPU specifies how many compute units will be reserved by a task
running with that profile; 1 CPU represents 1024 compute units. The value for
memory indicates how much RAM (in MB) will be reserved for the task.

You may also want to add other profile types (e.g., a hi-cpu type). The slug
you specify for the profile can then be referenced by build tasks deployed on
the BeeKeeper cluster.

Github
~~~~~~

Last, go to the repository you want to manage with BeeKeeper, go to Settings,
then Webhooks, and add a new webhook for
`https://<your app name>.herokuapp.com/github/notify>`. When prompted for a
secret, you can generate one using Python::

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

When the webhook is created, it will ping your BeeKeeper instance. This should
result in BeeKeeper responding and recording the existence of the project.
Any user logged in as an admin should see the project listed on the BeeKeeper
homepage. If you approve the project, any PR or repository push will start a
build as described in the `beekeeper.yml` file in the project home directory.

Documentation
-------------

Documentation for BeeKeeper can be found on `Read The Docs`_.

Community
---------

BeeKeeper is part of the `BeeWare suite`_. You can talk to the community through:

* `@pybeeware on Twitter`_

* The `pybee/general`_ channel on Gitter.

We foster a welcoming and respectful community as described in our
`BeeWare Community Code of Conduct`_.

Contributing
------------

If you experience problems with BeeKeeper, `log them on GitHub`_. If you
want to contribute code, please `fork the code`_ and `submit a pull request`_.

.. _BeeWare suite: http://pybee.org
.. _Read The Docs: http://pybee-beekeeper.readthedocs.io
.. _@pybeeware on Twitter: https://twitter.com/pybeeware
.. _pybee/general: https://gitter.im/pybee/general
.. _BeeWare Community Code of Conduct: http://pybee.org/community/behavior/
.. _log them on Github: https://github.com/pybee/beekeeper/issues
.. _fork the code: https://github.com/pybee/beekeeper
.. _submit a pull request: https://github.com/pybee/beekeeper/pulls
