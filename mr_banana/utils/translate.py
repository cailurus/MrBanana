from __future__ import annotations

from urllib.parse import quote

from mr_banana.utils.logger import logger


def _normalize_target_lang(lang: str) -> str:
    s = (lang or "").strip()
    if s in {"en", "zh-CN", "zh-TW"}:
        return s
    return "zh-CN"


def _google_lang(lang: str) -> str:
    # Google's unofficial endpoint tends to accept BCP-47-ish values.
    return {
        "zh-CN": "zh-CN",
        "zh-TW": "zh-TW",
        "en": "en",
    }.get(lang, "zh-CN")


def _deepl_lang(lang: str) -> str:
    # DeepL expects e.g. EN, ZH, ZH-HANS, ZH-HANT
    return {
        "en": "EN",
        "zh-CN": "ZH-HANS",
        "zh-TW": "ZH-HANT",
    }.get(lang, "ZH-HANS")


def translate_text(
    text: str | None,
    *,
    target_lang: str,
    provider: str = "google",
    base_url: str = "",
    api_key: str = "",
    email: str = "",
    proxy_url: str = "",
    timeout_sec: float = 15.0,
) -> str | None:
    """Translate a string.

    Providers:
    - google: best-effort via Google's unauthenticated endpoint.
    - microsoft: best-effort via Microsoft's Edge translate endpoint.
    - deepl: official API (requires api_key).

    Returns translated text or the original on failure.
    """
    if not text:
        return text

    provider = (provider or "google").strip().lower()
    target = _normalize_target_lang(target_lang)

    try:
        # curl_cffi is already used in this repo; keep consistent.
        from curl_cffi import requests  # type: ignore
    except Exception:
        logger.warning("translate: curl_cffi not available; skip")
        return text

    proxies = None
    if proxy_url:
        pu = str(proxy_url).strip()
        if pu:
            proxies = {"http": pu, "https": pu}

    if provider == "deepl":
        key = str(api_key or "").strip()
        if not key:
            logger.warning("translate deepl: missing api key; skip")
            return text
        try:
            # DeepL uses a different host for free keys (ending with :fx).
            host = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
            url = (base_url or "").strip().rstrip("/") or host
            resp = requests.post(
                url=f"{url}/v2/translate",
                data={
                    "auth_key": key,
                    "text": text,
                    "target_lang": _deepl_lang(target),
                },
                timeout=timeout_sec,
                verify=False,
                impersonate="chrome",
                proxies=proxies,
            )
            if resp.status_code != 200:
                logger.warning(f"translate deepl http={resp.status_code}")
                return text
            data = resp.json() if hasattr(resp, "json") else {}
            translations = (data or {}).get("translations")
            if isinstance(translations, list) and translations:
                t0 = translations[0]
                if isinstance(t0, dict):
                    out = t0.get("text")
                    return out or text
            return text
        except Exception as e:
            logger.warning(f"translate deepl failed: {e}")
            return text

    if provider == "microsoft":
        # Best-effort endpoint used by Edge; may change over time.
        try:
            url = "https://api-edge.cognitive.microsofttranslator.com/translate?api-version=3.0"
            url += f"&to={quote(target)}"
            resp = requests.post(
                url=url,
                json=[{"Text": text}],
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "user-agent": "Mozilla/5.0",
                },
                timeout=timeout_sec,
                verify=False,
                impersonate="chrome",
                proxies=proxies,
            )
            if resp.status_code != 200:
                logger.warning(f"translate microsoft http={resp.status_code}")
                return text
            data = resp.json() if hasattr(resp, "json") else None
            if isinstance(data, list) and data:
                translations = (data[0] or {}).get("translations")
                if isinstance(translations, list) and translations:
                    out = (translations[0] or {}).get("text")
                    return out or text
            return text
        except Exception as e:
            logger.warning(f"translate microsoft failed: {e}")
            return text

    # Default: google
    try:
        q = quote(text)
        tl = quote(_google_lang(target))
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={tl}&dt=t&q={q}"
        resp = requests.get(url=url, timeout=timeout_sec, verify=False, impersonate="chrome", proxies=proxies)
        if resp.status_code != 200:
            logger.warning(f"translate google http={resp.status_code}")
            return text
        data = resp.json() if hasattr(resp, "json") else None
        # Format: [[['translated','orig',...], ...], ...]
        if isinstance(data, list) and data and isinstance(data[0], list):
            parts = []
            for seg in data[0]:
                if isinstance(seg, list) and seg:
                    parts.append(str(seg[0] or ""))
            out = "".join(parts).strip()
            return out or text
        return text
    except Exception as e:
        logger.warning(f"translate google failed: {e}")
        return text
