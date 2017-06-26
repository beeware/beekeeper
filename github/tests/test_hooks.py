import json
import os

from django.test import TestCase

from ..models import User as GithubUser, Repository, PullRequest, Commit

from ..hooks import pull_request_handler, push_handler


class PullRequestHookTests(TestCase):
    def setUp(self):
        with open(os.path.join(os.path.dirname(__file__), 'pr_1.json')) as pr_file:
            self.payload = json.load(pr_file)

    def assert_postconditions(self, extra_users=0):
        # Postcondition - 2 users, 1 repo, 1 PR.
        self.assertEqual(GithubUser.objects.count(), 2 + extra_users)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 1)
        self.assertEqual(Commit.objects.count(), 1)

        # Check some properties of the created objects.
        submitter = GithubUser.objects.get(login='freakboy3742')
        self.assertEqual(submitter.github_id, 37345)
        self.assertEqual(submitter.avatar_url, 'https://avatars2.githubusercontent.com/u/37345?v=3')
        self.assertEqual(submitter.html_url, 'https://github.com/freakboy3742')
        self.assertEqual(submitter.user_type, GithubUser.USER_TYPE_USER)

        owner = GithubUser.objects.get(login='pybee')
        self.assertEqual(owner.github_id, 5001767)
        self.assertEqual(owner.avatar_url, 'https://avatars3.githubusercontent.com/u/5001767?v=3')
        self.assertEqual(owner.html_url, 'https://github.com/pybee')
        self.assertEqual(owner.user_type, GithubUser.USER_TYPE_ORGANIZATION)

        repo = Repository.objects.get(github_id=95284391)
        self.assertEqual(repo.owner, owner)
        self.assertEqual(repo.name, 'webhook-trigger')
        self.assertEqual(repo.html_url, 'https://github.com/pybee/webhook-trigger')
        self.assertEqual(repo.description, 'A test repository that can be used to test Github web hooks')

        commit = Commit.objects.get(sha='936ce824549a2a794df739c1ffab91f5644d812b')
        self.assertEqual(commit.user.login, 'freakboy3742')
        self.assertEqual(commit.branch, 'prtest')
        self.assertEqual(commit.url, 'https://github.com/pybee/webhook-trigger/commit/936ce824549a2a794df739c1ffab91f5644d812b')

        pr = PullRequest.objects.get(github_id=127348414)
        self.assertEqual(pr.user, submitter)
        self.assertEqual(pr.repository, repo)
        self.assertEqual(pr.number, 1)
        self.assertEqual(pr.title, 'Test of a pull request from a fork.')
        self.assertEqual(pr.html_url, 'https://github.com/pybee/webhook-trigger/pull/1')
        self.assertEqual(pr.diff_url, 'https://github.com/pybee/webhook-trigger/pull/1.diff')
        self.assertEqual(pr.patch_url, 'https://github.com/pybee/webhook-trigger/pull/1.patch')
        self.assertEqual(pr.state, PullRequest.STATE_OPEN)


    def test_clean_db(self):
        # Preconditions - a clean database
        self.assertEqual(GithubUser.objects.count(), 0)
        self.assertEqual(Repository.objects.count(), 0)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 0)

        pull_request_handler(self.payload)

        self.assert_postconditions()

    def test_existing_submitter(self):
        # Preconditions - an existing submitter.
        # Details are different; they will be updated.
        GithubUser.objects.create(
            github_id=37345,
            login='old_submitter_login',
            avatar_url='http://example.com/submitter/avatar',
            html_url='http://example.com/submitter/old_html_url',
            user_type=GithubUser.USER_TYPE_ORGANIZATION,
        )

        self.assertEqual(GithubUser.objects.count(), 1)
        self.assertEqual(Repository.objects.count(), 0)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 0)

        pull_request_handler(self.payload)

        self.assert_postconditions()

    def test_existing_owner(self):
        # Preconditions - an existing submitter.
        # Details are different; they will be updated.
        GithubUser.objects.create(
            github_id=5001767,
            login='old_owner_login',
            avatar_url='http://example.com/owner/avatar',
            html_url='http://example.com/owner/old_html_url',
            user_type=GithubUser.USER_TYPE_USER,
        )

        self.assertEqual(GithubUser.objects.count(), 1)
        self.assertEqual(Repository.objects.count(), 0)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 0)

        pull_request_handler(self.payload)

        self.assert_postconditions()

    def test_existing_repository(self):
        # Preconditions - an existing repository.
        # Details are different; they will be updated.
        old_owner = GithubUser.objects.create(
            github_id=999,
            login='old_owner',
            avatar_url='http://example.com/avatar',
            html_url='http://example.com/old_html_url',
            user_type=GithubUser.USER_TYPE_USER,
        )

        Repository.objects.create(
            github_id=95284391,
            owner=old_owner,
            name='old-name',
            html_url='http://example.com/old_html_url',
            description='Old description',
        )

        self.assertEqual(GithubUser.objects.count(), 1)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 0)

        pull_request_handler(self.payload)

        self.assert_postconditions(extra_users=1)

        old_owner = GithubUser.objects.get(github_id=999)
        self.assertEqual(old_owner.repositories.count(), 0)
        self.assertEqual(old_owner.pull_requests.count(), 0)

    def test_existing_pull_request(self):
        # Preconditions - an existing pull request.
        # Details are different; they will be updated.

        owner = GithubUser.objects.create(
            github_id=37345,
            login='old_submitter_login',
            avatar_url='http://example.com/submitter/avatar',
            html_url='http://example.com/submitter/old_html_url',
            user_type=GithubUser.USER_TYPE_ORGANIZATION,
        )
        repo = Repository.objects.create(
            github_id=95284391,
            owner=owner,
            name='old-name',
            html_url='http://example.com/old_html_url',
            description='Old description',
        )

        submitter = GithubUser.objects.create(
            github_id=5001767,
            login='old_owner_login',
            avatar_url='http://example.com/owner/avatar',
            html_url='http://example.com/owner/old_html_url',
            user_type=GithubUser.USER_TYPE_USER,
        )

        commit = Commit.objects.create(
            repository=repo,
            user=owner,
            branch='prtest',
            sha='936ce824549a2a794df739c1ffab91f5644d812b',
            url='https://github.com/pybee/webhook-trigger/commit/936ce824549a2a794df739c1ffab91f5644d812b'
        )

        PullRequest.objects.create(
            github_id=127348414,
            user=submitter,
            repository=repo,
            number=42,
            title="pr title",
            html_url='http://example.com/pr/42',
            diff_url='http://example.com/pr/42.diff',
            patch_url='http://example.com/pr/42.patch',
            commit=commit,
            state=PullRequest.STATE_OPEN,
        )
        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 1)
        self.assertEqual(Commit.objects.count(), 1)

        pull_request_handler(self.payload)

        self.assert_postconditions()


class PullHookTests(TestCase):
    def setUp(self):
        with open(os.path.join(os.path.dirname(__file__), 'pr_2.json')) as pr_file:
            self.pull_request_payload = json.load(pr_file)

        with open(os.path.join(os.path.dirname(__file__), 'pull_1.json')) as pull_file:
            self.pull_payload = json.load(pull_file)

    def assert_postconditions(self):
        commit = Commit.objects.get(sha='02bc552855735a0a4f74bfe2d8d2011bc003460c')
        self.assertEqual(commit.user.login, 'freakboy3742')
        self.assertEqual(commit.branch, 'master')
        self.assertEqual(commit.message, 'Merge pull request #2 from freakboy3742/closed_pr\n\nAdded content that can be merged.')
        self.assertEqual(commit.url, 'https://github.com/pybee/webhook-trigger/commit/02bc552855735a0a4f74bfe2d8d2011bc003460c')

    def test_standalone_commit(self):
        # Handle the pull request
        push_handler(self.pull_payload)

        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 1)

        self.assert_postconditions()

    def test_merge_commit(self):
        # Handle the pull request
        pull_request_handler(self.pull_request_payload)

        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 1)
        self.assertEqual(Commit.objects.count(), 1)

        push_handler(self.pull_payload)

        # An extra commit is created.
        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 1)
        self.assertEqual(Commit.objects.count(), 2)

        self.assert_postconditions()

    def test_merge_commit_before_pr(self):
        # Handle the pull request
        push_handler(self.pull_payload)

        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 0)
        self.assertEqual(Commit.objects.count(), 1)

        pull_request_handler(self.pull_request_payload)

        # An extra commit is created.
        self.assertEqual(GithubUser.objects.count(), 2)
        self.assertEqual(Repository.objects.count(), 1)
        self.assertEqual(PullRequest.objects.count(), 1)
        self.assertEqual(Commit.objects.count(), 2)

        self.assert_postconditions()

