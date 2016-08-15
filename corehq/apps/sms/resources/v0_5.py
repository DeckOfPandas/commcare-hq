import json
from collections import namedtuple
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.domain.models import Domain
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import SelfRegistrationInvitation
from corehq.apps.users.models import Permissions
from corehq import privileges
from django.http import HttpResponse, Http404
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.validation import Validation


FieldDefinition = namedtuple('FieldDefinition', 'name required type')


class SelfRegistrationApiException(Exception):
    pass


class SelfRegistrationValidationException(Exception):
    def __init__(self, errors):
        self.errors = errors
        super(SelfRegistrationValidationException, self).__init__('')


class SelfRegistrationUserInfo(object):

    def __eq__(self, other):
        """
        Allow comparison of two of these objects for use in tests.
        """
        if isinstance(other, self.__class__):
            return all(
                [getattr(self, prop) == getattr(other, prop)
                 for prop in ('phone_number', 'custom_user_data')]
            )

        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __init__(self, phone_number, custom_user_data=None):
        self.phone_number = phone_number
        self.custom_user_data = custom_user_data


class SelfRegistrationInfo(object):
    def __init__(self, app_id, android_only=False, require_email=False, custom_registration_message=None):
        self.app_id = app_id
        self.android_only = android_only
        self.require_email = require_email
        self.custom_registration_message = custom_registration_message
        self.users = []

    def add_user(self, user_info):
        """
        :param user_info: should be an instance of SelfRegistrationUserInfo
        """
        self.users.append(user_info)


class UserSelfRegistrationValidation(Validation):

    def _validate_toplevel_fields(self, data, field_defs):
        """
        :param data: any dictionary of data
        :param field_defs: a list of FieldDefinition namedtuples representing the names
        and types of the fields to validate
        """
        for field_def in field_defs:
            if field_def.name not in data and field_def.required:
                raise SelfRegistrationValidationException(
                    {field_def.name: 'This field is required'}
                )

            if field_def.name in data:
                if not isinstance(data[field_def.name], field_def.type):
                    raise SelfRegistrationValidationException(
                        {field_def.name: 'Expected type: {}'.format(field_def.type.__name__)}
                    )

    def _validate_app_id(self, domain, app_id):
        try:
            get_app(domain, app_id, latest=True)
        except Http404:
            raise SelfRegistrationValidationException({'app_id': 'Invalid app_id specified'})

    def _validate_users(self, user_data):
        phone_numbers = set()
        for user_info in user_data:
            if not isinstance(user_info, dict):
                raise SelfRegistrationValidationException(
                    {'users': 'Expected a list of dictionaries'}
                )

            self._validate_toplevel_fields(user_info, [
                FieldDefinition('phone_number', True, basestring),
                FieldDefinition('custom_user_data', False, dict),
            ])

            phone_number = apply_leniency(user_info['phone_number'])
            if phone_number in phone_numbers:
                raise SelfRegistrationValidationException(
                    {'users': 'phone_number cannot be reused within a request: {}'.format(phone_number)}
                )
            phone_numbers.add(phone_number)

    def is_valid(self, bundle, request=None):
        if not request:
            raise SelfRegistrationApiException('Expected request to be present')

        try:
            self._validate_toplevel_fields(bundle.data, [
                FieldDefinition('app_id', True, basestring),
                FieldDefinition('users', True, list),
                FieldDefinition('android_only', False, bool),
                FieldDefinition('require_email', False, bool),
                FieldDefinition('custom_registration_message', False, basestring),
            ])

            self._validate_app_id(request.domain, bundle.data['app_id'])
            self._validate_users(bundle.data['users'])
        except SelfRegistrationValidationException as e:
            return e.errors

        return {}


class UserSelfRegistrationResource(HqBaseResource):
    registration_result = None

    class Meta:
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        resource_name = 'sms_user_registration'
        allowed_methods = ['post']
        validation = UserSelfRegistrationValidation()

    def dispatch(self, request_type, request, **kwargs):
        domain_obj = Domain.get_by_name(request.domain)

        if not domain_has_privilege(domain_obj, privileges.INBOUND_SMS):
            raise ImmediateHttpResponse(
                HttpResponse(
                    json.dumps({'error': 'Your current plan does not have access to this feature'}),
                    content_type='application/json',
                    status=401
                )
            )
        elif not domain_obj.sms_mobile_worker_registration_enabled:
            raise ImmediateHttpResponse(
                HttpResponse(
                    json.dumps({'error': 'Please first enable SMS mobile worker registration for your project.'}),
                    content_type='application/json',
                    status=403
                )
            )
        else:
            return super(UserSelfRegistrationResource, self).dispatch(request_type, request, **kwargs)

    def full_hydrate(self, bundle):
        if not self.is_valid(bundle):
            raise ImmediateHttpResponse(response=self.error_response(bundle.request, bundle.errors))

        data = bundle.data

        custom_registration_message = data.get('custom_registration_message')
        if isinstance(custom_registration_message, basestring):
            custom_registration_message = custom_registration_message.strip()
            if not custom_registration_message:
                custom_registration_message = None

        obj = SelfRegistrationInfo(
            data.get('app_id'),
            data.get('android_only', False),
            data.get('require_email', False),
            custom_registration_message
        )
        for user_info in data.get('users', []):
            obj.add_user(SelfRegistrationUserInfo(
                user_info.get('phone_number'),
                user_info.get('custom_user_data')
            ))
        bundle.obj = obj
        return bundle

    def obj_create(self, bundle, **kwargs):
        bundle = self.full_hydrate(bundle)
        self.registration_result = SelfRegistrationInvitation.initiate_workflow(
            bundle.request.domain,
            bundle.obj.users,
            app_id=bundle.obj.app_id,
            custom_first_message=bundle.obj.custom_registration_message,
            android_only=bundle.obj.android_only,
            require_email=bundle.obj.require_email,
        )
        return bundle

    def post_list(self, request, **kwargs):
        super(UserSelfRegistrationResource, self).post_list(request, **kwargs)
        success_numbers, invalid_format_numbers, numbers_in_use = self.registration_result

        return HttpResponse(
            json.dumps({
                'success_numbers': success_numbers,
                'invalid_format_numbers': invalid_format_numbers,
                'numbers_in_use': numbers_in_use,
            }),
            content_type='application/json',
        )

    def detail_uri_kwargs(self, bundle_or_obj):
        return {}
