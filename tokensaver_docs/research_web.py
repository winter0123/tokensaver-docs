"""Capture narrowly authorized public HTML without inheriting proxy or auth settings."""
import http.client
import ipaddress
import re
import socket
import time
from urllib.parse import quote, urlsplit

WEB_LIMIT = 2 * 1024 * 1024


def normalize_domain(host):
    host = host.rstrip('.').encode('idna').decode('ascii').lower()
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}', host):
        raise ValueError('Use an exact public hostname, for example docs.example.org.')
    return host


def public_target(url, domains):
    parts = urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None or
            parts.password is not None or parts.port not in (None, 443) or parts.query or
            len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url)):
        return None
    host = normalize_domain(parts.hostname)
    if host not in domains:
        return None
    return host, quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError('Snapshot destination has a non-public address.')
    if not addresses:
        raise ValueError('Snapshot destination did not resolve.')
    return addresses[0][4][0]


def fetch_html(host, path):
    address = public_address(host)
    connection = http.client.HTTPSConnection(host, timeout=4)
    # Connect to the inspected IP. HTTPSConnection still verifies the original host.
    connection._create_connection = lambda _address, timeout, source_address: socket.create_connection(
        (address, 443), timeout, source_address)
    try:
        deadline = time.monotonic() + 8
        connection.request('GET', path, headers={'Accept': 'text/html', 'Accept-Encoding': 'identity',
                                                 'User-Agent': 'TokenSaverDocs'})
        response = connection.getresponse()
        if (response.status != 200 or response.headers.get_content_type() not in ('text/html', 'application/xhtml+xml')
                or response.headers.get('Content-Encoding', 'identity').lower() != 'identity'):
            raise ValueError('Snapshot requires a direct HTML response with identity encoding.')
        lengths = response.headers.get_all('Content-Length', [])
        expected = None
        if lengths:
            if len(lengths) != 1 or response.chunked or not re.fullmatch(r'[0-9]+', lengths[0].strip()):
                raise ValueError('Snapshot returned an ambiguous Content-Length.')
            expected = int(lengths[0])
            if expected > WEB_LIMIT:
                raise ValueError('HTML snapshot exceeds 2 MiB.')
        content = bytearray()
        while time.monotonic() < deadline:
            chunk = response.read1(min(65536, WEB_LIMIT + 1 - len(content)))
            if not chunk:
                if expected is not None and len(content) != expected:
                    raise ValueError('Snapshot response ended before its declared Content-Length.')
                if not content:
                    raise ValueError('Snapshot response was empty.')
                return bytes(content)
            content.extend(chunk)
            if len(content) > WEB_LIMIT:
                raise ValueError('HTML snapshot exceeds 2 MiB.')
        raise ValueError('HTML snapshot exceeded the time budget.')
    finally:
        connection.close()
