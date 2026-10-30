"""Is this the address of a model server this site may call? (the SSRF guard, docs/CUSTOM-MODEL-DESIGN.md section 5)

https only (plain http only when private addresses are allowed), no credentials in the URL, and the name must resolve only to
public addresses. Returns the address that was checked so the call can be pinned to it."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class ModelError(RuntimeError):
    """A failure with a message that is safe to show the learner (never contains their key)."""


def check_base_url(url: str, allow_private: bool = False, resolver=None):
    """Returns (scheme, host, port, path, ip) for a usable address, or raises ModelError saying why not."""
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ModelError("That model address is not a valid web address.")
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ModelError("The model address must start with https:// and name a server.")
    if parts.scheme == "http" and not allow_private:
        raise ModelError("The model address must start with https://.")
    if parts.username or parts.password:
        raise ModelError("Leave the user name and password out of the address; put the key in the key box.")
    if parts.query or parts.fragment:
        raise ModelError("The model address should be the base address only, for example https://api.openai.com/v1.")
    host = parts.hostname
    resolver = resolver or socket.getaddrinfo
    try:
        infos = resolver(host, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        raise ModelError("That server name could not be found.")
    ips = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        ips.append(ip)
    if not ips:
        raise ModelError("That server name could not be found.")
    if not allow_private:
        for ip in ips:
            if not ip.is_global or ip.is_multicast:
                raise ModelError("That address points inside a private network, which this site will not call.")
    return parts.scheme, host, port or (443 if parts.scheme == "https" else 80), parts.path.rstrip("/"), str(ips[0])
