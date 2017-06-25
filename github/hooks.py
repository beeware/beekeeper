
def ping_handler(payload):
    "A handler for the Github Ping message"
    return 'OK'


def pull_request_handler(payload):
    "A handler for pull request messages"
    # Make sure we have a record for the submitter of the PR
    from .models import User as GithubUser, Repository, PullRequest

    user_data = payload['pull_request']['user']
    try:
        submitter = GithubUser.objects.get(github_id=user_data['id'])
    except GithubUser.DoesNotExist:
        submitter = GithubUser(github_id=user_data['id'])

    submitter.login = user_data['login']
    submitter.avatar_url = user_data['avatar_url']
    submitter.html_url = user_data['html_url']
    submitter.user_type = GithubUser.USER_TYPE_VALUES[user_data['type']]
    submitter.save()

    # Make sure we have a record for the repository owner
    user_data = payload['repository']['owner']
    try:
        owner = GithubUser.objects.get(github_id=user_data['id'])
    except GithubUser.DoesNotExist:
        owner = GithubUser(github_id=user_data['id'])

    owner.login = user_data['login']
    owner.avatar_url = user_data['avatar_url']
    owner.html_url = user_data['html_url']
    owner.user_type = GithubUser.USER_TYPE_VALUES[user_data['type']]
    owner.save()

    # Make sure we have a record for the repository
    repo_data = payload['repository']
    try:
        repo = Repository.objects.get(github_id=repo_data['id'])
    except Repository.DoesNotExist:
        repo = Repository(github_id=repo_data['id'])

    repo.owner = owner
    repo.name = repo_data['name']
    repo.html_url = repo_data['html_url']
    repo.description = repo_data['description']
    repo.save()

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
    pr.save()

    return 'OK'
