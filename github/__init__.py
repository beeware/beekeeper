
def ping_handler(payload):
    "A handler for the Github Ping message"
    return 'OK'

hooks = {
    'ping': ping_handler
}
