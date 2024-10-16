"""Prepare py.test."""
import json
import os
import socket
import time
from base64 import b64encode
from sys import platform
from urllib.parse import quote_plus

import betamax
import pytest
from betamax.serializers import JSONSerializer


# Prevent calls to sleep
def _sleep(*args):
    raise Exception("Call to sleep")


time.sleep = _sleep


def b64_string(input_string):
    """Return a base64 encoded string (not bytes) from input_string."""
    return b64encode(input_string.encode("utf-8")).decode("utf-8")


def env_default(key):
    """Return environment variable or placeholder string."""
    return os.environ.get(
        f"PRAWCORE_{key.upper()}",
        "http://localhost:8080" if key == "redirect_uri" else f"fake_{key}",
    )


def filter_access_token(interaction, current_cassette):
    """Add Betamax placeholder to filter access token."""
    request_uri = interaction.data["request"]["uri"]
    response = interaction.data["response"]
    if "api/v1/access_token" not in request_uri or response["status"]["code"] != 200:
        return
    body = response["body"]["string"]
    try:
        token = json.loads(body)["access_token"]
    except (KeyError, TypeError, ValueError):
        return
    current_cassette.placeholders.append(
        betamax.cassette.cassette.Placeholder(
            placeholder="<ACCESS_TOKEN>", replace=token
        )
    )


def two_factor_callback():
    """Return an OTP code."""
    return None


placeholders = {
    x: env_default(x)
    for x in (
        "client_id client_secret password permanent_grant_code temporary_grant_code"
        " redirect_uri refresh_token user_agent username"
    ).split()
}


placeholders["basic_auth"] = b64_string(
    f"{placeholders['client_id']}:{placeholders['client_secret']}"
)


class PrettyJSONSerializer(JSONSerializer):
    name = "prettyjson"

    def serialize(self, cassette_data):
        return f"{json.dumps(cassette_data, sort_keys=True, indent=2, separators=(',', ': '))}\n"


betamax.Betamax.register_serializer(PrettyJSONSerializer)
with betamax.Betamax.configure() as config:
    config.cassette_library_dir = "tests/integration/cassettes"
    config.default_cassette_options["serialize_with"] = "prettyjson"
    config.before_record(callback=filter_access_token)
    for key, value in placeholders.items():
        if key == "password":
            value = quote_plus(value)
        config.define_cassette_placeholder(f"<{key.upper()}>", value)


class Placeholders:
    def __init__(self, _dict):
        self.__dict__ = _dict


def pytest_configure():
    pytest.placeholders = Placeholders(placeholders)


if platform == "darwin":  # Work around issue with betamax on OS X
    socket.gethostbyname = lambda x: "127.0.0.1"
