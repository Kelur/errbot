import json
import logging
import os
import pytest
import requests
import socket
from errbot.backends.test import FullStackTest
from time import sleep

log = logging.getLogger(__name__)

PYTHONOBJECT = ['foo', {'bar': ('baz', None, 1.0, 2)}]
JSONOBJECT = json.dumps(PYTHONOBJECT)
# Webserver port is picked based on the process ID so that when tests
# are run in parallel with pytest-xdist, each process runs the server
# on a different port
WEBSERVER_PORT = 5000 + (os.getpid() % 1000)
WEBSERVER_SSL_PORT = WEBSERVER_PORT + 1000


def webserver_ready(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        return True
    except:
        return False


class TestWebhooks(FullStackTest):

    def setUp(self, extra_plugin_dir=None, extra_test_file=None, loglevel=logging.DEBUG):
        super().setUp(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webhooks_tests'),
                      extra_test_file)
        self.bot.push_message("!plugin config Webserver " +
                              "{{'HOST': 'localhost', 'PORT': {}, 'SSL':  None}}".format(WEBSERVER_PORT))
        self.bot.pop_message()
        while not webserver_ready('localhost', WEBSERVER_PORT):
            log.debug("Webserver not ready yet, sleeping 0.1 second")
            sleep(0.1)

    def test_not_configured_url_returns_404(self):
        assert requests.post(
            'http://localhost:{}/randomness_blah'.format(WEBSERVER_PORT),
            "{'toto': 'titui'}"
        ).status_code == 404

    def test_webserver_plugin_ok(self):
        self.bot.push_message("!webstatus")
        assert "/echo" in self.bot.pop_message()

    def test_trailing_no_slash_ok(self):
        assert requests.post(
            'http://localhost:{}/echo'.format(WEBSERVER_PORT),
            JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_trailing_slash_also_ok(self):
        assert requests.post(
            'http://localhost:{}/echo/'.format(WEBSERVER_PORT),
            JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_json_is_automatically_decoded(self):
        assert requests.post(
            'http://localhost:{}/webhook1'.format(WEBSERVER_PORT),
            JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_json_on_custom_url_is_automatically_decoded(self):
        assert requests.post(
            'http://localhost:{}/custom_webhook'.format(WEBSERVER_PORT),
            JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_post_form_data_on_webhook_without_form_param_is_automatically_decoded(self):
        assert requests.post(
            'http://localhost:{}/webhook1'.format(WEBSERVER_PORT),
            data=JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_post_form_data_on_webhook_with_custom_url_and_without_form_param_is_automatically_decoded(self):
        assert requests.post(
            'http://localhost:{}/custom_webhook'.format(WEBSERVER_PORT),
            data=JSONOBJECT
        ).text == repr(json.loads(JSONOBJECT))

    def test_webhooks_with_form_parameter_decode_json_automatically(self):
        form = {'form': JSONOBJECT}
        assert requests.post(
            'http://localhost:{}/form'.format(WEBSERVER_PORT),
            data=form
        ).text == repr(json.loads(JSONOBJECT))

    def test_webhooks_with_form_parameter_on_custom_url_decode_json_automatically(self):
        form = {'form': JSONOBJECT}
        assert requests.post(
            'http://localhost:{}/custom_form'.format(WEBSERVER_PORT),
            data=form
        ).text, repr(json.loads(JSONOBJECT))

    def test_webhooks_with_raw_request(self):
        form = {'form': JSONOBJECT}
        assert requests.post(
            'http://localhost:{}/raw'.format(WEBSERVER_PORT),
            data=form
        ).text == "<class 'bottle.LocalRequest'>"

    def test_generate_certificate_creates_usable_cert(self):
        d = self.bot.bot_config.BOT_DATA_DIR
        key_path = os.sep.join((d, "webserver_key.pem"))
        cert_path = os.sep.join((d, "webserver_certificate.pem"))

        self.bot.push_message("!generate_certificate")
        assert "Generating" in self.bot.pop_message(timeout=1)

        # Generating a certificate could be slow on weak hardware, so keep a safe
        # timeout on the first pop_message()
        assert "successfully generated" in self.bot.pop_message(timeout=60)
        assert "is recommended" in self.bot.pop_message(timeout=1)
        assert key_path in self.bot.pop_message(timeout=1)

        webserver_config = {
            'HOST': 'localhost',
            'PORT': WEBSERVER_PORT,
            'SSL': {
                'certificate': cert_path,
                'key': key_path,
                'host': 'localhost',
                'port': WEBSERVER_SSL_PORT,
                'enabled': True,
            }
        }
        self.bot.push_message("!plugin config Webserver {!r}".format(webserver_config))
        self.bot.pop_message()

        while not webserver_ready('localhost', WEBSERVER_SSL_PORT):
            log.debug("Webserver not ready yet, sleeping 0.1 second")
            sleep(0.1)

        assert requests.post(
            'https://localhost:{}/webhook1'.format(WEBSERVER_SSL_PORT),
            JSONOBJECT,
            verify=False
        ).text == repr(json.loads(JSONOBJECT))

    def test_custom_headers_and_status_codes(self):
        assert requests.post(
            'http://localhost:{}/webhook6'.format(WEBSERVER_PORT)
        ).headers['X-Powered-By'] == "Err"

        assert requests.post(
            'http://localhost:{}/webhook7'.format(WEBSERVER_PORT)
        ).status_code == 403
