"""
Unit tests for the DomainTools DXL service which do not require a DomainTools
account or a DXL broker.
"""
import json
import os
import shutil
import tempfile
import unittest

from mock import MagicMock

from domaintools import API
from domaintools.exceptions import ServiceException
from dxlbootstrap.util import MessageUtils
from dxlclient.message import Request, Message
from dxldomaintoolsservice import DomainToolsService
from dxldomaintoolsservice.requesthandlers import DomainToolsRequestCallback

APP_CONFIG = """[General]
apiKey=test-api-key
apiUser=test-user
"""


class DomainToolsServiceTest(unittest.TestCase):

    def setUp(self):
        self.config_dir = tempfile.mkdtemp()
        with open(os.path.join(self.config_dir,
                               "dxldomaintoolsservice.config"), "w") as f:
            f.write(APP_CONFIG)

    def tearDown(self):
        shutil.rmtree(self.config_dir)

    def test_load_configuration(self):
        app = DomainToolsService(self.config_dir)
        app._load_configuration()
        self.assertIsInstance(app.domaintools_api, API)
        self.assertEqual("test-user", app.domaintools_api.username)

    def test_missing_api_key_raises(self):
        with open(os.path.join(self.config_dir,
                               "dxldomaintoolsservice.config"), "w") as f:
            f.write("[General]\napiUser=test-user\n")
        app = DomainToolsService(self.config_dir)
        with self.assertRaises(Exception):
            app._load_configuration()


class DomainToolsRequestCallbackTest(unittest.TestCase):

    def _run_request(self, callback, payload):
        request = Request("/opendxl-domaintools/service/domaintools/whois")
        if payload is not None:
            MessageUtils.dict_to_json_payload(request, payload)
        callback.on_request(request)
        callback._app.client.send_response.assert_called_once()
        return callback._app.client.send_response.call_args[0][0]

    def _create_app(self, api):
        app = MagicMock()
        app.domaintools_api = api
        return app

    def test_request_invokes_api_and_returns_data(self):
        api = MagicMock()
        api.whois.return_value.data.return_value = {
            "response": {"registrant": "Example Registrant"}}
        callback = DomainToolsRequestCallback(self._create_app(api), "whois",
                                              ["query"])

        response = self._run_request(callback, {"query": "example.local"})

        api.whois.assert_called_once_with(query="example.local", format="json")
        self.assertEqual(Message.MESSAGE_TYPE_RESPONSE, response.message_type)
        self.assertEqual(
            {"response": {"registrant": "Example Registrant"}},
            MessageUtils.json_payload_to_dict(response))

    def test_missing_required_parameter_returns_error(self):
        api = MagicMock()
        callback = DomainToolsRequestCallback(self._create_app(api), "whois",
                                              ["query"])

        response = self._run_request(callback, {})

        api.whois.assert_not_called()
        self.assertEqual(Message.MESSAGE_TYPE_ERROR, response.message_type)
        self.assertIn("Required parameter not found: 'query'",
                      MessageUtils.decode(response.error_message))

    def test_unsupported_format_returns_error(self):
        api = MagicMock()
        callback = DomainToolsRequestCallback(self._create_app(api), "whois",
                                              ["query"])

        response = self._run_request(callback,
                                     {"query": "example.local", "format": "csv"})

        api.whois.assert_not_called()
        self.assertEqual(Message.MESSAGE_TYPE_ERROR, response.message_type)
        self.assertIn("Unsupported format requested: 'csv'",
                      MessageUtils.decode(response.error_message))

    def test_service_exception_returns_error(self):
        api = MagicMock()
        api.whois.side_effect = ServiceException(403, "Not authorized")
        callback = DomainToolsRequestCallback(self._create_app(api), "whois",
                                              ["query"])

        response = self._run_request(callback, {"query": "example.local"})

        self.assertEqual(Message.MESSAGE_TYPE_ERROR, response.message_type)
        self.assertEqual("ServiceException: Not authorized",
                         MessageUtils.decode(response.error_message))


if __name__ == "__main__":
    unittest.main()
