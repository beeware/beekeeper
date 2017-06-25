from .hooks import ping_handler, pull_request_handler

default_app_config = 'github.apps.GithubConfig'

hooks = {
    'ping': ping_handler,
    'pull_request': pull_request_handler,
}
