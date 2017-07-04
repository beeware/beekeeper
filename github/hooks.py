from dateutil import parser as datetime_parser


def get_or_create_user(user_data):
    "Extract and update a user from payload data"
    from .models import User as GithubUser

    try:
        user = GithubUser.objects.get(github_id=user_data['id'])
    except GithubUser.DoesNotExist:
        user = GithubUser(github_id=user_data['id'])

    user.login = user_data['login']
    user.avatar_url = user_data['avatar_url']
    user.html_url = user_data['html_url']
    user.user_type = GithubUser.USER_TYPE_VALUES[user_data['type']]
    user.save()

    return user


def get_or_create_repository(repo_data):
    from .models import Repository

    # Make sure we have a record for the owner of the repository
    owner = get_or_create_user(repo_data['owner'])

    try:
        repo = Repository.objects.get(github_id=repo_data['id'])
    except Repository.DoesNotExist:
        repo = Repository(github_id=repo_data['id'])

    repo.owner = owner
    repo.name = repo_data['name']
    repo.html_url = repo_data['html_url']
    repo.description = repo_data['description']
    repo.save()

    return repo


def ping_handler(payload):
    "A handler for the Github Ping message"

    # Make sure we have a record for the repository
    repo = get_or_create_repository(payload['repository'])

    return 'OK'


def push_handler(payload):
    "A handler for Github push messages"
    from .models import Commit, Push
    from .signals import new_build

    # Make sure we have a record for the submitter of the pull
    user = get_or_create_user(payload['sender'])

    # Make sure we have a record for the repository
    repo = get_or_create_repository(payload['repository'])

    # Make sure we have a record for the commit
    commit_data = payload['head_commit']
    try:
        commit = Commit.objects.get(sha=commit_data['id'])
    except Commit.DoesNotExist:
        commit = Commit(sha=commit_data['id'])

    commit.repository = repo
    commit.user = user
    commit.branch = payload['ref'].rsplit('/', 1)[1]
    commit.message = commit_data['message']
    commit.url = commit_data['url']
    commit.created = datetime_parser.parse(commit_data['timestamp'])
    commit.save()

    # And create a push record.
    try:
        push = Push.objects.get(commit=commit)
    except Push.DoesNotExist:
        push = Push(commit=commit)
    push.created = datetime_parser.parse(commit_data['timestamp'])
    push.save()

    new_build.send(sender=Push, push=push)

    return 'OK'


def pull_request_handler(payload):
    "A handler for pull request messages"
    from .models import Commit, PullRequest, PullRequestUpdate
    from .signals import new_build

    # Make sure we have a record for the submitter of the PR
    submitter = get_or_create_user(payload['pull_request']['user'])

    # Make sure we have a record for the repository
    repo = get_or_create_repository(payload['repository'])

    # Make sure we have a record of the head commit
    commit_sha = payload['pull_request']['head']['sha']
    try:
        commit = Commit.objects.get(sha=commit_sha)
    except Commit.DoesNotExist:
        commit = Commit.objects.create(
            repository=repo,
            sha=commit_sha,
            user=submitter,
            branch=payload['pull_request']['head']['ref'],
            created=datetime_parser.parse(payload['pull_request']['updated_at']),
            url='https://github.com/%s/%s/commit/%s' % (
                repo.owner.login,
                repo.name,
                commit_sha
            )
        )

    # Make sure we have a record for the PR
    pr_data = payload['pull_request']
    try:
        pr = PullRequest.objects.get(github_id=pr_data['id'])
    except PullRequest.DoesNotExist:
        pr = PullRequest(github_id=pr_data['id'])

    pr.user = submitter
    pr.repository = repo
    pr.number = pr_data['number']
    pr.html_url = pr_data['html_url']
    pr.diff_url = pr_data['diff_url']
    pr.patch_url = pr_data['patch_url']
    pr.state = PullRequest.STATE_VALUES[pr_data['state']]
    pr.title = pr_data['title']
    pr.created = datetime_parser.parse(pr_data['created_at'])
    pr.updated = datetime_parser.parse(pr_data['updated_at'])
    pr.save()

    # And create a pull request update for this PR.
    try:
        update = PullRequestUpdate.objects.get(pull_request=pr, commit=commit)
    except PullRequestUpdate.DoesNotExist:
        update = PullRequestUpdate(
            pull_request=pr,
            commit=commit,
        )
    update.created = datetime_parser.parse(pr_data['created_at'])
    update.save()

    if payload['action'] in ['opened', 'synchronize']:
        new_build.send(sender=PullRequestUpdate, update=update)
    elif payload['action'] == 'closed':
        for change in pr.changes.active():
            change.complete()

    return 'OK'
