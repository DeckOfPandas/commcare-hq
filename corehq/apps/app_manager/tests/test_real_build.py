import os
from unittest import SkipTest

import requests
from django.test import SimpleTestCase
from requests.auth import HTTPDigestAuth

from corehq.apps.app_manager.models import Application


class TestRealBuild(SimpleTestCase):

    def fetch_and_build_app(self, domain, app_id):
        try:
            username = os.environ['TRAVIS_HQ_USERNAME']
            password = os.environ['TRAVIS_HQ_PASSWORD']
        except KeyError as err:
            if os.environ.get("TRAVIS") == "true":
                raise
            raise SkipTest("not travis (KeyError: {})".format(err))

        url = "https://www.commcarehq.org/a/{}/apps/source/{}/".format(
            domain, app_id
        )
        response = requests.get(url, auth=HTTPDigestAuth(username, password))
        if response.status_code == 401 and not os.environ.get("TRAVIS_SECURE_ENV_VARS") == "true":
            # on travis this test fails for non-dimagi repos because encrypted variables don't work
            # see https://docs.travis-ci.com/user/environment-variables/#Defining-encrypted-variables-in-.travis.yml
            raise SkipTest("Not running TestRealBuild from external PR from {}".format(
                os.environ.get('TRAVIS_REPO_SLUG')
            ))

        response.raise_for_status()
        app = Application.wrap(response.json())
        app.create_all_files()

    def test_real_build(self):
        self.fetch_and_build_app('commcare-tests', 'ae3c6e073262360f89d2630cfd220bd3')
