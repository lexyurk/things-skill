import http.client
import io
import json
import unittest
import urllib.error

from things_cloud.errors import CloudError, ThingsError, UncertainWrite
from things_cloud.protocol import Cloud, NoRedirect, strict_json


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Opener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return Response(json.dumps(self.response).encode() if isinstance(self.response, dict) else self.response)


class TransportTests(unittest.TestCase):
    def test_auth_encodes_unicode_reserved_characters_and_does_not_send_password_on_history(self):
        cloud = Cloud()
        cloud.opener = Opener({"history-key": "secret/history?capability"})
        cloud.authenticate("me+things@example.com", "pass word/é?#%")
        req = cloud.opener.requests[0]
        self.assertTrue(req.full_url.endswith("/account/me%2Bthings%40example.com"))
        self.assertEqual(req.get_header("Authorization"), "Password pass%20word%2F%C3%A9%3F%23%25")
        cloud.opener.response = {"items": [], "current-item-index": 0}
        cloud.page(0)
        req = cloud.opener.requests[-1]
        self.assertNotIn("Authorization", req.headers)
        self.assertIn("secret%2Fhistory%3Fcapability", req.full_url)

    def test_commit_has_checked_ancestor_single_part_and_schema_headers(self):
        cloud = Cloud("capability", "instance")
        cloud.opener = Opener({"server-head-index": 8})
        self.assertEqual(cloud.commit({"id": {"e": "Task7", "t": 1, "p": {"tt": "é"}}}, 7), 8)
        req = cloud.opener.requests[0]
        self.assertTrue(req.full_url.endswith("/commit?ancestor-index=7&_cnt=1"))
        self.assertEqual(req.get_header("Schema"), "301")
        self.assertEqual(req.get_header("Push-priority"), "5")
        self.assertEqual(req.get_header("Content-type"), "application/json; charset=UTF-8")
        self.assertEqual(json.loads(req.data)["id"]["p"]["tt"], "é")

    def test_http_errors_never_expose_capabilities_passwords_or_response_bodies(self):
        cloud = Cloud("secret-capability")
        for status in (401, 403, 409, 429):
            cloud.opener = Opener(
                urllib.error.HTTPError("https://secret-capability", status, "secret-password", {}, io.BytesIO(b"secret task body"))
            )
            with self.assertRaises(CloudError) as error:
                cloud.page(1)
            self.assertNotIn("secret", str(error.exception))
        cloud.opener = Opener(urllib.error.HTTPError("https://secret", 503, "Secret", {}, io.BytesIO()))
        with self.assertRaises(UncertainWrite):
            cloud.commit({}, 0)

    def test_truncated_reads_and_bad_json_make_posts_uncertain(self):
        cloud = Cloud("capability")
        for failure in (
            b"invalid",
            http.client.IncompleteRead(b"private data"),
            b'{"server-head-index":1,"server-head-index":2}',
            b'{"server-head-index":NaN}',
        ):
            cloud.opener = Opener(failure)
            with self.assertRaises(UncertainWrite):
                cloud.commit({}, 0)
        cloud.opener = Opener(http.client.IncompleteRead(b"private data"))
        with self.assertRaises(ThingsError) as error:
            cloud.page(0)
        self.assertNotIn("private", str(error.exception))

    def test_redirects_are_never_followed_with_account_secrets(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://untrusted.example"))

    def test_strict_json_rejects_duplicates_and_nonfinite_values(self):
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json(value)


if __name__ == "__main__":
    unittest.main()
