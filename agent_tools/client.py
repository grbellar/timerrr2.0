"""HTTP client: account tokens stay in the local process, never in MCP output."""

import os
import time
import uuid
from urllib.parse import urlsplit

import requests


class TimerrrClient:
    def __init__(self):
        self.base_url = os.environ.get("TIMERRR_URL", "https://timerrr.com").rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http"
            and parsed.hostname in ("localhost", "127.0.0.1", "::1")
        ):
            raise ValueError("TIMERRR_URL must use HTTPS, except on localhost.")
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
        ):
            raise ValueError(
                "TIMERRR_URL must be an origin without credentials, path, query, or fragment."
            )
        self.token = os.environ.get("TIMERRR_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Set TIMERRR_TOKEN to a token created in Timerrr Agent work."
            )

    def call(self, action, data=None, mutation=False):
        data = dict(data or {})
        if mutation:
            data.setdefault("request_id", str(uuid.uuid4()))
        for attempt in range(3):
            try:
                response = requests.post(
                    self.base_url + "/api/agent/" + action,
                    json=data,
                    headers={"Authorization": "Bearer " + self.token},
                    timeout=(5, 10),
                    allow_redirects=False,
                )
                if response.status_code >= 500:
                    raise requests.ConnectionError("Server temporarily unavailable.")
                if response.status_code != 200:
                    try:
                        message = response.json().get("error", "Request failed.")
                    except ValueError:
                        message = (
                            "Unexpected response. Check TIMERRR_URL and your token."
                        )
                    raise ValueError(message)
                return response.json()
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise ValueError(
                        "Timerrr is unavailable. Retry with the same request_id."
                    ) from None
                time.sleep(0.2 * (attempt + 1))
