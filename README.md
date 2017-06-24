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
    $ heroku scale worker=1
    $ heroku run ./manage.py migrate
    $ heroku run ./manage.py createsuperuser

Github
~~~~~~

Next, go to the repository you want to manage, go to Settings, then Webhooks,
and add a new webhook for
`https:<your app name>.herokuapp.com/github/notify>`. When prompted for a secret,
generate one::

    >>> from django.utils.crypto import get_random_string
    >>> get_random_string(50)
    'nuiVypAArY7lFDgMdyC5kwutDGQdDc6rXljuIcI5iBttpPebui'

Once the webhook has been created, set the GITHUB_WEBHOOK_KEY variable to this
string::

    $ heroku config:set GITHUB_WEBHOOK_KEY=<your key here>

and put::

    GITHUB_WEBHOOK_KEY=<your key here>

In the .env file in the project home directory.

Sendgrid
~~~~~~~~

Sign up for a Sendgrid account, then get an API key. Set that key on Heroku::

    $ heroku config:set SENDGRID_API_KEY=<your key here>

and put::

    SENDGRID_API_KEY=<your key here>

In the .env file in the project home directory.

Amazon AWS
~~~~~~~~~~

Log into (or sign up for) your Amazon AWS account:

Set that key on Heroku::

    $ heroku config:set AWS_ACCESS_KEY_ID=<your key here>
    $ heroku config:set AWS_SECRET_ACCESS_KEY=<your secret key here>

and put::

    AWS_ACCESS_KEY_ID=<your key here>
    AWS_SECRET_ACCESS_KEY=<your secret key here>

In the .env file in the project home directory.
