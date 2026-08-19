"""Phase 0 fixtures: path shim, env loading, access-code default, live-test skip, headers_ok."""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from core.paths import load_dotenv

load_dotenv()
os.environ.setdefault("ACCESS_CODE", "test-code")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip_live = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def headers_ok() -> dict:
    return {"X-Access-Code": os.environ["ACCESS_CODE"]}
