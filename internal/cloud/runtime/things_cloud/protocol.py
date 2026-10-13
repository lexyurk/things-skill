"""Evidence-backed Things Cloud v1 HTTP transport. Never logs capability URLs."""

import base64
import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .errors import CloudError, ThingsError, UncertainWrite

BASE_URL = "https://cloud.culturedcode.com/version/1"
MAX_RESPONSE = 64 * 1024 * 1024


def strict_json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Non-finite JSON number")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Cloud:
    def __init__(self, history_key=None, instance_id="things-cloud-plugin", timeout=30):
        self.history_key = history_key
        self.timeout = timeout
        self.instance_id = instance_id
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, path, body=None, password=None):
        info = {
            "dm": "Linux",
            "lr": "US",
            "nf": True,
            "nk": True,
            "nn": "ThingsMac",
            "nv": "32209501",
            "on": "Linux",
            "ov": "1",
            "pl": "en-US",
            "ul": "en-Latn-US",
        }
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "UTF-8",
            "User-Agent": "ThingsMac/32209501",
            "Schema": "301",
            "App-Id": "com.culturedcode.ThingsMac",
            "App-Instance-Id": self.instance_id,
            "Things-Client-Info": base64.b64encode(json.dumps(info).encode()).decode(),
        }
        if password is not None:
            headers["Authorization"] = "Password " + urllib.parse.quote(password, safe="")
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            headers.update({"Content-Type": "application/json; charset=UTF-8", "Content-Encoding": "UTF-8", "Push-Priority": "5"})
        req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = response.read(MAX_RESPONSE + 1)
                if len(payload) > MAX_RESPONSE:
                    raise ValueError("Oversized response")
                result = strict_json(payload.decode("utf-8"))
                if not isinstance(result, dict):
                    raise ValueError("Expected object")
                return result
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            # A 5xx POST may have been committed before the error reached us.
            if method == "POST" and status >= 500:
                raise UncertainWrite("Cloud write outcome is unknown; sync to reconcile it before another write.") from None
            raise CloudError(status) from None
        except (OSError, socket.timeout, urllib.error.URLError, http.client.HTTPException, ValueError, UnicodeError):
            if method == "POST":
                raise UncertainWrite("Cloud write outcome is unknown; sync to reconcile it before another write.") from None
            raise ThingsError("Unable to read Things Cloud. Check the connection and try again.") from None

    def authenticate(self, email, password):
        if not email.strip() or not password:
            raise ThingsError("Email and password are required.")
        result = self.request("GET", "/account/" + urllib.parse.quote(email.strip(), safe=""), password=password)
        key = result.get("history-key")
        if not isinstance(key, str) or not key or len(key) > 512:
            raise ThingsError("Account has no usable sync history. Check Things Cloud settings in Things.")
        self.history_key = key
        return key

    def history_path(self):
        if not self.history_key:
            raise ThingsError("No account connected. Run: things-cloud connect")
        return "/history/" + urllib.parse.quote(self.history_key, safe="")

    def page(self, index):
        return self.request("GET", self.history_path() + f"/items?start-index={index}")

    def commit(self, changes, ancestor):
        result = self.request("POST", self.history_path() + f"/commit?ancestor-index={ancestor}&_cnt=1", body=changes)
        head = result.get("server-head-index")
        if type(head) is not int or head <= ancestor:
            raise UncertainWrite("Cloud returned no valid commit index; sync to reconcile the write.")
        return head
