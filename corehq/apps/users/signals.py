from __future__ import absolute_import
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.contrib.auth.signals import user_logged_in
from corehq.apps.users.models import CouchUser
from corehq.elastic import send_to_elasticsearch


commcare_user_post_save = Signal(providing_args=["couch_user"])
couch_user_post_save = Signal(providing_args=["couch_user"])


@receiver(user_logged_in)
def set_language(sender, **kwargs):
    """
    Whenever a user logs in, attempt to set their browser session
    to the right language.
    HT: http://mirobetm.blogspot.com/2012/02/django-language-set-in-database-field.html
    """
    user = kwargs['user']
    couch_user = CouchUser.from_django_user(user)
    if couch_user and couch_user.language:
        kwargs['request'].session['django_language'] = couch_user.language


# Signal that syncs django_user => couch_user
def django_user_post_save_signal(sender, instance, created, **kwargs):
    return CouchUser.django_user_post_save_signal(sender, instance, created)


def update_user_in_es(sender, couch_user, **kwargs):
    """
    Automatically sync the user to elastic directly on save or delete
    """
    send_to_elasticsearch("users", couch_user.to_json(),
                          delete=couch_user.to_be_deleted())


# This gets called by UsersAppConfig when the module is set up
def connect_user_signals():
    post_save.connect(django_user_post_save_signal, User,
                      dispatch_uid="django_user_post_save_signal")
    couch_user_post_save.connect(update_user_in_es, dispatch_uid="update_user_in_es")
