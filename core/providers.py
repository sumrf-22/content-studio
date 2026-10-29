"""OpenAI-compatible provider adapter used by the live LLM path.

One request shape covers OpenRouter, SenseNova, OmniRoute and any custom
OpenAI-compatible gateway: ``POST {base_url}/chat/completions`` with a Bearer
token. 429 and 5xx responses are retried with exponential backoff; timeouts and
auth failures become sanitized ``ProviderError`` messages that never contain
the key.
"""

import time

import requests

import core.settings as settings

RETRY_STATUS = {429, 500, 502, 503, 504}
DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT = 60


class ProviderError(RuntimeError):
    """A provider call failed; the message is safe to show to the operator."""


def _sleep(seconds):
    time.sleep(seconds)


def _sanitize(text, secret):
    text = str(text or "")
    if secret:
        text = text.replace(secret, "[redacted]")
    text = " ".join(text.split())
    return text[:300]


def _error_detail(response, secret):
    """Best-effort short upstream message, never including the key."""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    detail = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or error.get("code") or ""
        elif isinstance(error, str):
            detail = error
        detail = detail or payload.get("message") or ""

    detail = _sanitize(detail, secret)
    return f" ({detail})" if detail else ""


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, min(float(retry_after), 5.0))
        except ValueError:
            pass
    return 0.5 * (2 ** attempt)


def chat(
    provider,
    messages,
    *,
    timeout=DEFAULT_TIMEOUT,
    attempts=DEFAULT_ATTEMPTS,
    max_tokens=None,
):
    """Return the assistant text from one OpenAI-compatible completion."""
    name = provider.get("name") or provider.get("id") or "provider"
    base_url = str(provider.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ProviderError(f"Provider {name!r} has no base URL.")

    try:
        api_key = settings.decrypt_key(provider.get("api_key"))
    except settings.SettingsError as exc:
        raise ProviderError(f"Provider {name!r}: {exc}") from exc

    url = base_url + "/chat/completions"
    body = {
        "model": provider.get("model"),
        "messages": messages,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            response = requests.post(
                url, headers=headers, json=body, timeout=timeout
            )
        except requests.Timeout as exc:
            raise ProviderError(
                f"Provider {name!r} timed out after {timeout}s."
            ) from exc
        except requests.RequestException as exc:
            # The exception text can include the URL but not the Authorization
            # header; still sanitize defensively.
            last_error = _sanitize(exc, api_key)
            if attempt + 1 < attempts:
                _sleep(0.5 * (2 ** attempt))
                continue
            raise ProviderError(
                f"Provider {name!r} could not be reached: {last_error}"
            ) from exc

        status = response.status_code

        if status in RETRY_STATUS and attempt + 1 < attempts:
            _sleep(_retry_delay(response, attempt))
            continue

        if status == 401:
            raise ProviderError(
                f"Provider {name!r} rejected the API key (HTTP 401)."
            )
        if status == 403:
            raise ProviderError(
                f"Provider {name!r} refused the request (HTTP 403)."
            )
        if status == 404:
            raise ProviderError(
                f"Provider {name!r} returned HTTP 404; check the base URL "
                "and model."
            )
        if status == 429:
            raise ProviderError(
                f"Provider {name!r} is still rate limited (HTTP 429) after "
                f"{attempts} attempts."
            )
        if status >= 500:
            raise ProviderError(
                f"Provider {name!r} returned HTTP {status} after "
                f"{attempts} attempts."
            )
        if status >= 400:
            raise ProviderError(
                f"Provider {name!r} rejected the request (HTTP {status})"
                + _error_detail(response, api_key)
                + "."
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Provider {name!r} returned an unexpected response shape."
            ) from exc

        if not isinstance(content, str):
            raise ProviderError(
                f"Provider {name!r} returned no text content."
            )
        return content

    raise ProviderError(
        f"Provider {name!r} failed after {attempts} attempts: {last_error}"
    )


def test_provider(provider):
    """Minimal real request used by the Settings Test button."""
    content = chat(
        provider,
        [{"role": "user", "content": "Reply with the single word OK."}],
        timeout=15,
        attempts=2,
        max_tokens=16,
    )
    return {
        "ok": True,
        "provider_id": provider.get("id"),
        "message": "Provider responded successfully.",
        "reply": content.strip()[:80],
    }
