import html
import re
import unicodedata
from urllib.parse import urlsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

def clean_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\S\r\n]{2,}", " ", text)
    return text.strip()

def extract_real_url(url: str) -> str:
    if not url:
        return ""
    try:
        if "news.google.com" in url.lower():
            parsed = urlsplit(url)
            params = dict(parse_qsl(parsed.query))
            if "url" in params:
                return params["url"]
            try:
                import requests as req_lib
                resp = req_lib.head(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }, allow_redirects=False, timeout=5)
                location = resp.headers.get("Location")
                if location:
                    return location
            except Exception:
                pass
        return url
    except Exception:
        return url

def fetch_og_image(url: str, timeout: int = 4) -> str:
    if not url:
        return ""
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        })
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace")
        match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1))
        match = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', body, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1))
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if match and not match.group(1).startswith("data:"):
            src = match.group(1)
            if src.startswith("//"):
                parsed = urlsplit(url)
                src = f"{parsed.scheme}:{src}"
            elif src.startswith("/"):
                parsed = urlsplit(url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            return src
    except Exception:
        pass
    return ""

SOURCE_THUMBS = {
    "G1": "https://www.google.com/s2/favicons?domain=g1.globo.com&sz=64",
    "UOL": "https://www.google.com/s2/favicons?domain=uol.com.br&sz=64",
    "Terra": "https://www.google.com/s2/favicons?domain=terra.com.br&sz=64",
    "Folha": "https://www.google.com/s2/favicons?domain=folha.uol.com.br&sz=64",
    "R7": "https://www.google.com/s2/favicons?domain=r7.com&sz=64",
    "Band": "https://www.google.com/s2/favicons?domain=band.uol.com.br&sz=64",
    "Estadão": "https://www.google.com/s2/favicons?domain=estadao.com.br&sz=64",
    "Correio Braziliense": "https://www.google.com/s2/favicons?domain=correiobraziliense.com.br&sz=64",
    "O Globo": "https://www.google.com/s2/favicons?domain=oglobo.globo.com&sz=64",
    "Gazeta do Povo": "https://www.google.com/s2/favicons?domain=gazetadopovo.com.br&sz=64",
    "CNN Brasil": "https://www.google.com/s2/favicons?domain=cnnbrasil.com.br&sz=64",
    "Metrópoles": "https://www.google.com/s2/favicons?domain=metropoles.com&sz=64",
    "Google News": "https://www.google.com/s2/favicons?domain=news.google.com&sz=64",
}

def get_source_thumb(source: str) -> str:
    if not source:
        return ""
    return SOURCE_THUMBS.get(source, "")

def enrich_news_item(item: dict) -> dict:
    raw_url = item.get("url", "")
    real_url = extract_real_url(raw_url)
    item["url"] = real_url or raw_url
    if "title" in item:
        item["title"] = clean_text(item["title"])
    if "snippet" in item:
        item["snippet"] = clean_text(item["snippet"])
    if not item.get("image_url"):
        thumb = fetch_og_image(real_url or raw_url)
        if thumb:
            item["image_url"] = thumb
        else:
            fallback = get_source_thumb(item.get("source", ""))
            if fallback:
                item["image_url"] = fallback
    return item
