"""Tests for AzuraCast HTTP retry helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from config import Config
from http_retry import request_with_retries


def _cfg(**kw: object) -> Config:
    base = dict(
        azura_api_key="k",
        station_id=1,
        base_url="http://example/api",
        openai_api_key="o",
        elevenlabs_api_key="e",
        voice_id="v",
        remote_dir="ai_voiceovers",
        poll_interval_sec=15,
        segment_rem_min=40,
        segment_rem_max=70,
        upload_index_wait_sec=5,
        post_segment_sleep_sec=70,
        openai_model="gpt-4o-mini",
        elevenlabs_tts_model="eleven_multilingual_v2",
        request_timeout_sec=10.0,
        http_retry_max=3,
        http_retry_backoff_sec=0.0,
        script_max_chars=1200,
    )
    base.update(kw)
    return Config(**base)


def _response(status: int, text: str = "") -> MagicMock:
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.ok = 200 <= status < 300
    r.text = text
    return r


@patch("http_retry.time.sleep", lambda *_: None)
@patch("http_retry.requests.request")
def test_retry_stops_on_401_no_extra_calls(mock_req):
    mock_req.return_value = _response(401, "unauthorized")
    c = _cfg(http_retry_max=3)
    out = request_with_retries(
        "GET", "http://example/api/x", config=c, context="t", headers={}
    )
    assert out is not None
    assert out.status_code == 401
    assert mock_req.call_count == 1


@patch("http_retry.time.sleep", lambda *_: None)
@patch("http_retry.requests.request")
def test_retries_503_until_success(mock_req):
    mock_req.side_effect = [
        _response(503, "bad"),
        _response(503, "bad"),
        _response(200, "{}"),
    ]
    c = _cfg(http_retry_max=3)
    out = request_with_retries(
        "GET", "http://example/api/x", config=c, context="t", headers={}
    )
    assert out is not None
    assert out.ok
    assert mock_req.call_count == 3


@patch("http_retry.time.sleep", lambda *_: None)
@patch("http_retry.requests.request")
def test_connection_error_retries_then_none(mock_req):
    mock_req.side_effect = [
        requests.ConnectionError("refused"),
        requests.ConnectionError("refused"),
        requests.ConnectionError("refused"),
    ]
    c = _cfg(http_retry_max=2)
    out = request_with_retries(
        "GET", "http://example/api/x", config=c, context="t", headers={}
    )
    assert out is None
    assert mock_req.call_count == 3
