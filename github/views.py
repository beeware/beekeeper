import hmac
from hashlib import sha1
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import requests
from ipaddress import ip_address, ip_network


@require_POST
@csrf_exempt
def webhook(request):
    # Verify if request came from GitHub
    forwarded_for = u'{}'.format(request.META.get('HTTP_X_FORWARDED_FOR'))
    client_ip_address = ip_address(forwarded_for)
    whitelist = requests.get('https://api.github.com/meta').json()['hooks']

    for valid_ip in whitelist:
        if client_ip_address in ip_network(valid_ip):
            break
    else:
        return HttpResponseForbidden('Permission denied.')

    # Verify the request signature
    header_signature = request.META.get('HTTP_X_HUB_SIGNATURE')
    if header_signature is None:
        return HttpResponseForbidden('Permission denied.')

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha1':
        return HttpResponseServerError('Operation not supported.', status=501)

    mac = hmac.new(
        settings.GITHUB_WEBHOOK_KEY.encode('utf-8'),
        msg=request.body,
        digestmod=sha1
    )
    if not hmac.compare_digest(mac.hexdigest().encode('utf-8'), signature.encode('utf-8')):
        return HttpResponseForbidden('Permission denied.')

    # If request reached this point we are in a good shape
    # Process the GitHub events
    event = request.META.get('HTTP_X_GITHUB_EVENT', 'ping')

    payload = json.loads(request.body.decode('utf-8'))
    if event == 'ping':
        print("GITHUB PONG", payload)
        return HttpResponse('OK')
    elif event == 'push':
        # Deploy some code for example
        print("GITHUB PUSH")
        return HttpResponse('OK')

    # In case we receive an event that's not ping or push
    return HttpResponse(status=204)
