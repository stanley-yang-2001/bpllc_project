"""HTTP connections that go to an address that was already checked, while the certificate and the Host header are for the real name."""
from __future__ import annotations

import http.client
import socket
import ssl


class _Pinned(http.client.HTTPSConnection):
    """HTTPS to an IP that was already checked, while the certificate and Host header are for the real name."""

    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedPlain(http.client.HTTPConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)
