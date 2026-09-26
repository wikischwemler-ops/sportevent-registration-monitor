import hashlib

import httpx
from bs4 import BeautifulSoup

from .config import settings


def fetch_page(url: str) -> tuple[str, str]:
    headers = {"User-Agent": settings.user_agent}
    with httpx.Client(timeout=settings.request_timeout_seconds, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text[:120_000], content_hash
