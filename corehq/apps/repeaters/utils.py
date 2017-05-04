import base64
from collections import OrderedDict
from django.conf import settings

from corehq.util.couch import DocUpdate
from dimagi.utils.modules import to_function


def get_all_repeater_types():
    return OrderedDict([
        (to_function(cls, failhard=True).__name__, to_function(cls, failhard=True)) for cls in settings.REPEATERS
    ])


def get_repeater_auth_header(headers, username, password):
    user_pass = base64.encodestring(':'.join((username, password))).replace('\n', '')
    return {'Authorization': 'Basic ' + user_pass}


def migrate_repeater(repeater_doc):
    if "use_basic_auth" in repeater_doc:
        use_basic_auth = repeater_doc['use_basic_auth'] is True
        del repeater_doc['use_basic_auth']
        if use_basic_auth:
            repeater_doc["auth_type"] = "basic"
        return DocUpdate(repeater_doc)
