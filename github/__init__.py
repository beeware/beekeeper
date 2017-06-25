from .hooks import ping_handler, pull_request_handler

hooks = {
    'ping': ping_handler,
    'pull_request': pull_request_handler,
}
