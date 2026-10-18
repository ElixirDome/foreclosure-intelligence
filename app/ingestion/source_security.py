"""Safe URL validation for administrator-configured ingestion sources."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


class UnsafeSourceURL(ValueError):
    """Raised when a configured source could target a non-public host."""


def validate_source_url(url: str, *, resolve_dns: bool = False) -> str:
    """Validate an HTTP(S) URL and optionally reject private DNS targets.

    DNS validation is repeated immediately before every fetch and redirect.
    This is defense in depth; production deployments should also enforce
    outbound network restrictions at the network/container level.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeSourceURL("A source URL is required.")

    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UnsafeSourceURL("The source URL is malformed.") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeSourceURL("Only HTTP and HTTPS source URLs are supported.")
    if not hostname or not parsed.netloc:
        raise UnsafeSourceURL("The source URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeSourceURL("Source URLs must not contain embedded credentials.")
    if parsed.fragment:
        raise UnsafeSourceURL("Source URLs must not contain fragments.")

    host = hostname.rstrip(".").lower()
    if (
        host == "localhost"
        or host.endswith((".localhost", ".local", ".internal", ".test"))
    ):
        raise UnsafeSourceURL("Local or internal hostnames are not allowed.")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None and not literal_ip.is_global:
        raise UnsafeSourceURL("Private, loopback, and reserved IP addresses are not allowed.")

    if resolve_dns and literal_ip is None:
        try:
            answers = socket.getaddrinfo(
                host,
                port or (443 if parsed.scheme.lower() == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise UnsafeSourceURL("The source hostname could not be resolved.") from exc

        addresses = set()
        for answer in answers:
            try:
                addresses.add(ipaddress.ip_address(answer[4][0]))
            except (ValueError, IndexError):
                continue

        if not addresses or any(not address.is_global for address in addresses):
            raise UnsafeSourceURL(
                "The source hostname resolves to a private or non-public address."
            )

    normalized = urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )
    return normalized


def safe_get(
    url: str,
    *,
    timeout: float = 20,
    headers: dict[str, str] | None = None,
    max_redirects: int = 5,
    max_bytes: int = 10 * 1024 * 1024,
) -> requests.Response:
    """Fetch a public URL while validating redirects and bounding response size."""
    current_url = validate_source_url(url, resolve_dns=True)

    for redirect_count in range(max_redirects + 1):
        response = requests.get(
            current_url,
            timeout=timeout,
            headers=headers,
            allow_redirects=False,
            stream=True,
        )

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise UnsafeSourceURL(
                    "The source returned a redirect without a destination."
                )
            if redirect_count >= max_redirects:
                raise UnsafeSourceURL("The source exceeded the redirect limit.")
            current_url = validate_source_url(
                urljoin(current_url, location),
                resolve_dns=True,
            )
            continue

        try:
            response.raise_for_status()
            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) > max_bytes:
                raise UnsafeSourceURL("The source response exceeds the size limit.")

            body = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise UnsafeSourceURL("The source response exceeds the size limit.")

            # Materialize only after enforcing the cap so callers can use
            # the familiar Response.text interface without unbounded reads.
            response._content = bytes(body)
            response._content_consumed = True
            return response
        except Exception:
            response.close()
            raise

    raise UnsafeSourceURL("The source exceeded the redirect limit.")
