"""AzuraCast HTTP calls with retries on network errors and 429/5xx (not on 401/403/404)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from typing import Any

import requests

from config import Config

logger = logging.getLogger(__name__)

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def log_http_failure(resp: requests.Response, context: str) -> None:
    """Log status and truncated body; never log request headers."""
    snippet = (resp.text or "")[:500].replace("\r", " ").replace("\n", " ")
    logger.warning("HTTP %s [%s]: %r", resp.status_code, context, snippet)


def request_with_retries(
    method: str,
    url: str,
    *,
    config: Config,
    context: str,
    **kwargs: Any,
) -> requests.Response | None:
    kwargs.setdefault("timeout", config.request_timeout_sec)

    def once() -> requests.Response:
        return requests.request(method, url, **kwargs)

    return request_callable_with_retries(once, config=config, context=context)


def request_callable_with_retries(
    call: Callable[[], requests.Response],
    *,
    config: Config,
    context: str,
) -> requests.Response | None:
    backoff = config.http_retry_backoff_sec
    max_r = config.http_retry_max
    last: requests.Response | None = None
    for attempt in range(max_r + 1):
        try:
            last = call()
        except requests.RequestException as exc:
            if attempt < max_r:
                logger.warning(
                    "%s: %s (attempt %s/%s), retry in %.1fs",
                    context,
                    exc,
                    attempt + 1,
                    max_r,
                    backoff,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.warning("%s: exhausted retries after error: %s", context, exc)
            return None

        assert last is not None
        if last.ok:
            return last

        code = last.status_code
        if code in (401, 403, 404):
            log_http_failure(last, context)
            return last
        if 400 <= code < 500 and code not in _RETRY_STATUS:
            log_http_failure(last, context)
            return last
        if code in _RETRY_STATUS and attempt < max_r:
            logger.warning(
                "HTTP %s [%s] attempt %s/%s, retry in %.1fs",
                code,
                context,
                attempt + 1,
                max_r,
                backoff,
            )
            time.sleep(backoff)
            backoff *= 2
            continue

        log_http_failure(last, context)
        return last
