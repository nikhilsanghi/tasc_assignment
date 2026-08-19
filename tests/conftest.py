"""Fixtures added in the phase their module first exists (see plan Sec1)."""
import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from core.paths import DATA, load_dotenv
from core.policy import default_rubric as _default_rubric, load_policy as _load_policy
from core.skills import load_aliases as _load_aliases, load_similarity as _load_similarity

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


@pytest.fixture
def candidates() -> list[dict]:
    return json.loads((DATA / "candidates_normalized.json").read_text())


@pytest.fixture
def roles() -> list[dict]:
    return json.loads((DATA / "roles_normalized.json").read_text())


@pytest.fixture
def role_r004(roles) -> dict:
    return next(r for r in roles if r["role_id"] == "R004")


@pytest.fixture
def policy() -> dict:
    return _load_policy()


@pytest.fixture
def aliases() -> dict:
    return _load_aliases()


@pytest.fixture
def similarity() -> dict:
    return _load_similarity()


@pytest.fixture
def default_rubric() -> dict:
    return _default_rubric(10)


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(*outputs):
        calls = []

        def stub(system_blocks, user_text, schema, stage, model=None):
            calls.append((system_blocks, user_text))
            if len(calls) > len(outputs):
                raise AssertionError("fake_llm called more times than outputs given")
            usage = {"input_tokens": 10, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
            return outputs[len(calls) - 1], usage

        monkeypatch.setattr("core.llm.call_structured", stub)
        stub.calls = calls
        return stub

    return _install
