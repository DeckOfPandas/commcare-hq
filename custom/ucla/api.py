from __future__ import absolute_import
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.users.models import WebUser
from corehq.form_processor.utils import is_commcarecase
from corehq.util.soft_assert import soft_assert


RISK_PROFILE_FIELD = 'risk_profile'
REQUIRED_FIXTURE_FIELDS = [RISK_PROFILE_FIELD, 'sequence', 'message']


def notify_dimagi_project_admins(domain, message):
    users = list(WebUser.get_dimagi_emails_by_domain(domain))
    # if there isn't a dimagi email in the project, notify admins
    notify_admins = len(users) == 0
    _assert = soft_assert(users, notify_admins=notify_admins, send_to_ops=False)
    _assert(False, message)


def ucla_message_bank_content(reminder, handler, recipient):
    domain = reminder.domain
    message_bank = FixtureDataType.by_domain_tag(domain, 'message_bank').first()

    if not message_bank:
        message = u"Lookup Table message_bank not found in {}".format(domain)
        notify_dimagi_project_admins(domain, message=message)
        return None

    fields = message_bank.fields_without_attributes

    if any(field not in fields for field in REQUIRED_FIXTURE_FIELDS):
        message = u"message_bank in {} must have {}".format(
            domain, ','.join(REQUIRED_FIXTURE_FIELDS)
        )
        notify_dimagi_project_admins(domain, message=message)
        return None

    if not is_commcarecase(recipient):
        recipient_id = getattr(recipient, '_id') if hasattr(recipient, '_id') else 'id_unknown'
        message = u"recipient {} must be a case in domain {}".format(recipient_id, domain)
        notify_dimagi_project_admins(domain, message=message)
        return None

    try:
        risk_profile = recipient.dynamic_case_properties()[RISK_PROFILE_FIELD]
    except KeyError:
        message = u"case {} does not include risk_profile".format(recipient.case_id)
        notify_dimagi_project_admins(domain, message=message)
        return None

    current_message_seq_num = str(
        ((reminder.schedule_iteration_num - 1) * len(handler.events)) +
        reminder.current_event_sequence_num + 1
    )
    custom_messages = FixtureDataItem.by_field_value(
        domain, message_bank, RISK_PROFILE_FIELD, risk_profile
    )
    custom_messages = filter(
        lambda m: m.fields_without_attributes['sequence'] == current_message_seq_num,
        custom_messages
    )

    if len(custom_messages) != 1:
        if not custom_messages:
            message = u"No message for risk {}, seq {} in domain {}"
        else:
            message = u"Multiple messages for risk {}, seq {} in domain {}"
        message = message.format(risk_profile, current_message_seq_num, domain)
        notify_dimagi_project_admins(domain, message=message)
        return None

    return custom_messages[0].fields_without_attributes['message']
