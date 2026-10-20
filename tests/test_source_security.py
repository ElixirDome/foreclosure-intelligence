import socket

import pytest

from app.ingestion.source_security import (
    UnsafeSourceURL,
    validate_source_url,
)


def test_validate_source_url_accepts_public_https_url():
    assert validate_source_url("https://example.com/auctions") == (
        "https://example.com/auctions"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/admin",
        "http://127.0.0.1:8000/",
        "http://10.0.0.12/private",
        "http://192.168.1.5/",
        "http://metadata.google.internal/",
        "http://user:password@example.com/",
    ],
)
def test_validate_source_url_rejects_unsafe_targets(url):
    with pytest.raises(UnsafeSourceURL):
        validate_source_url(url)


def test_validate_source_url_rejects_private_dns_results(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.20.30.40", 443),
            )
        ]

    monkeypatch.setattr(
        "app.ingestion.source_security.socket.getaddrinfo",
        fake_getaddrinfo,
    )

    with pytest.raises(UnsafeSourceURL, match="private or non-public"):
        validate_source_url("https://public-looking.example/auctions", resolve_dns=True)
