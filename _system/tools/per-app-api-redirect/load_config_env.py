#!/usr/bin/env python3
"""Print shell exports from config.json for the helper scripts."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path


def read_config() -> dict:
    config_path = Path(
        os.environ.get("CONFIG_PATH", Path(__file__).with_name("config.json"))
    )
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def emit(name: str, value: object) -> None:
    print(f"export {name}={shlex.quote(str(value))}")


def main() -> int:
    config = read_config()
    target = config.get("target", {})
    local = config.get("local", {})
    proxy = config.get("proxy", {})

    emit("APP_PATH", os.environ.get("APP_PATH", config.get("appPath", "")))
    emit("TARGET_SCHEME", os.environ.get("TARGET_SCHEME", target.get("scheme", "https")))
    emit("TARGET_HOST", os.environ.get("TARGET_HOST", target.get("host", "")))
    emit("LOCAL_SCHEME", os.environ.get("LOCAL_SCHEME", local.get("scheme", "http")))
    emit("LOCAL_HOST", os.environ.get("LOCAL_HOST", local.get("host", "127.0.0.1")))
    emit("LOCAL_PORT", os.environ.get("LOCAL_PORT", local.get("port", 8081)))
    emit("PROXY_HOST", os.environ.get("PROXY_HOST", proxy.get("host", "127.0.0.1")))
    emit("PROXY_PORT", os.environ.get("PROXY_PORT", proxy.get("port", 8080)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
