from __future__ import absolute_import
import base64
from collections import OrderedDict
from django.conf import settings

from dimagi.utils.modules import to_function


def get_all_repeater_types():
    return OrderedDict([
        (to_function(cls, failhard=True).__name__, to_function(cls, failhard=True)) for cls in settings.REPEATERS
    ])


def get_repeater_auth_header(headers, username, password):
    user_pass = base64.encodestring(':'.join((username, password))).replace('\n', '')
    return {'Authorization': 'Basic ' + user_pass}
