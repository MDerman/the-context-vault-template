"""mitmproxy addon: forward one public hostname to a local service.

The app still asks for TARGET_HOST, but mitmproxy forwards matching requests to
LOCAL_HOST:LOCAL_PORT. Paths, query strings, methods, and bodies are preserved.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mitmproxy import ctx
from mitmproxy import http


def read_config() -> dict:
    config_path = Path(os.environ.get("CONFIG_PATH", Path(__file__).with_name("config.json")))
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


CONFIG = read_config()
TARGET = CONFIG.get("target", {})
LOCAL = CONFIG.get("local", {})

TARGET_SCHEME = os.environ.get("TARGET_SCHEME", TARGET.get("scheme", "https"))
TARGET_HOST = os.environ.get("TARGET_HOST", TARGET.get("host", "api.lemonsqueezy.com"))
LOCAL_SCHEME = os.environ.get("LOCAL_SCHEME", LOCAL.get("scheme", "http"))
LOCAL_HOST = os.environ.get("LOCAL_HOST", LOCAL.get("host", "127.0.0.1"))
LOCAL_PORT = int(os.environ.get("LOCAL_PORT", LOCAL.get("port", 8081)))


def request(flow: http.HTTPFlow) -> None:
    if flow.request.scheme != TARGET_SCHEME or flow.request.pretty_host != TARGET_HOST:
        return

    original_url = flow.request.pretty_url
    flow.request.headers["X-Original-Host"] = TARGET_HOST
    flow.request.headers["X-Original-URL"] = original_url
    flow.request.scheme = LOCAL_SCHEME
    flow.request.host = LOCAL_HOST
    flow.request.port = LOCAL_PORT

    ctx.log.info(
        f"redirected {original_url} -> "
        f"{LOCAL_SCHEME}://{LOCAL_HOST}:{LOCAL_PORT}{flow.request.path}"
    )
