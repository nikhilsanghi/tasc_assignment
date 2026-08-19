from api._shared import dispatch
from api.health import handle


def test_health_ok(headers_ok):
    status, payload = dispatch(handle, headers_ok, {})
    assert status == 200
    assert payload["ok"] is True
    assert payload["data_loaded"] is True
    assert payload["prompts_dir"] is True


def test_health_no_header():
    status, payload = dispatch(handle, {}, {})
    assert status == 401
    assert payload == {"error": "unauthorized"}


def test_health_access_code_unset(monkeypatch, headers_ok):
    monkeypatch.delenv("ACCESS_CODE", raising=False)
    status, payload = dispatch(handle, headers_ok, {})
    assert status == 401
