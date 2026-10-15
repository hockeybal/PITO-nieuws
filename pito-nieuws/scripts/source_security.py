"""Small, dependency-free trust boundary for external source material.

``safe_external_url`` is a syntactic check for links; it does not resolve DNS.
Only ``fetch_public_https`` is suitable for downloading an untrusted URL. It
checks every resolved address and connects to a checked numeric address while
TLS still verifies the original hostname. No environment proxy is consulted.
"""

import http.client
import ipaddress
import math
import re
import socket
import ssl
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlsplit


_REDIRECTS = frozenset((301, 302, 303, 307, 308))
_FORBIDDEN_URL_CHARS = re.compile(r"[\x00-\x20\x7f-\x9f\\]")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z", re.I)
_XML_DECLARATION = re.compile(r"\A<\?xml\s+[^?]*\?>", re.I | re.ASCII)
_XML_ENCODING = re.compile(r"\bencoding\s*=\s*(['\"])([^'\"]+)\1", re.I | re.ASCII)
_XML_DECLARATIONS = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.I | re.ASCII)


@dataclass(frozen=True)
class _URL:
    hostname: str
    port: int
    target: str


@dataclass(frozen=True)
class _Address:
    family: int
    sockaddr: tuple


def _parse_https_url(url):
    if not isinstance(url, str) or not url or _FORBIDDEN_URL_CHARS.search(url):
        raise ValueError("Ongeldige HTTPS-bronlink")
    if any(character.isspace() for character in url):
        raise ValueError("Ongeldige HTTPS-bronlink")
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
            raise ValueError
        if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
            raise ValueError
        if parsed.netloc.endswith(":"):
            raise ValueError
        if parsed.netloc.startswith("[") and not re.fullmatch(r"\[[^\]]+\](?::[0-9]+)?", parsed.netloc):
            raise ValueError
        port = parsed.port if parsed.port is not None else 443
        if not 1 <= port <= 65535:
            raise ValueError
        hostname = parsed.hostname.encode("idna").decode("ascii").lower()
        if "%" in hostname:
            # Zone identifiers and percent-encoded hostnames are ambiguous.
            raise ValueError
        try:
            literal = ipaddress.ip_address(hostname)
            if parsed.netloc.startswith("[") and literal.version != 6:
                raise ValueError
        except ValueError:
            if parsed.netloc.startswith("[") or ":" in hostname or len(hostname) > 253:
                raise ValueError
            labels = hostname[:-1].split(".") if hostname.endswith(".") else hostname.split(".")
            if not all(_DNS_LABEL.fullmatch(label) for label in labels):
                raise ValueError
        target = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            target += "?" + quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
        return _URL(hostname, port, target)
    except (ValueError, UnicodeError):
        raise ValueError("Ongeldige HTTPS-bronlink") from None


def safe_external_url(url):
    """Whether a link is HTTPS, has a valid host and has no credentials/controls.

    This function deliberately does not perform a network operation. Escape
    the accepted value for its HTML attribute when rendering it.
    """
    try:
        _parse_https_url(url)
        return True
    except ValueError:
        return False


def _public_address(address):
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_private
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not getattr(address, "is_site_local", False)
    )


def _resolve_public(hostname, port):
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except OSError:
        raise ValueError("Bronhost kon niet veilig worden opgezocht") from None
    addresses = []
    for family, kind, protocol, _, sockaddr in results:
        if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
            raise ValueError("Onveilige bronhost")
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except (ValueError, TypeError, IndexError):
            raise ValueError("Onveilige bronhost") from None
        if not _public_address(address) or (family == socket.AF_INET6 and (len(sockaddr) != 4 or sockaddr[3])):
            raise ValueError("Bronhost verwijst niet uitsluitend naar publieke adressen")
        if family == socket.AF_INET and address.version != 4 or family == socket.AF_INET6 and address.version != 6:
            raise ValueError("Onveilige bronhost")
        # Reconstruct the numeric address, rather than reusing DNS input at connect time.
        pinned = (str(address), port) if family == socket.AF_INET else (str(address), port, 0, 0)
        addresses.append(_Address(family, pinned))
    if not addresses:
        raise ValueError("Bronhost heeft geen publiek adres")
    return addresses[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, port, address, timeout):
        # Default context enables CA verification and hostname checking.
        super().__init__(hostname, port, timeout=timeout, context=ssl.create_default_context())
        self._address = address
        self._abort_lock = threading.Lock()
        self._active_socket = None
        self._aborted = False
        # HTTPConnection stores its socket factory on the instance in __init__.
        # HTTPSConnection.connect keeps self.host for SNI and certificate checks.
        self._create_connection = self._connect_pinned

    def _connect_pinned(self, unused_address, timeout, source_address=None):
        with self._abort_lock:
            if self._aborted:
                raise TimeoutError("Bronverzoek duurde te lang")
            stream = socket.socket(self._address.family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            self._active_socket = stream
        try:
            stream.settimeout(timeout)
            if source_address is not None:
                stream.bind(source_address)
            stream.connect(self._address.sockaddr)
            return stream
        except BaseException:
            stream.close()
            raise

    def connect(self):
        http.client.HTTPConnection.connect(self)
        with self._abort_lock:
            if self._aborted:
                raise TimeoutError("Bronverzoek duurde te lang")
            # Retain the TLS socket before the blocking handshake, so a deadline
            # can abort it. Wrapping without a handshake does not read the peer.
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host, do_handshake_on_connect=False)
            self._active_socket = self.sock
        self.sock.do_handshake()

    def abort(self):
        with self._abort_lock:
            self._aborted = True
            if self._active_socket is not None:
                # close() alone does not interrupt a makefile() header/body read.
                try:
                    self._active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    self._active_socket.close()
                except OSError:
                    pass

    def close(self):
        with self._abort_lock:
            super().close()
            # http.client also calls close() when handing a Connection: close
            # response to its caller. Retain the socket for deadline shutdown
            # while HTTPResponse's makefile() can still be reading its body.


def _positive_size(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Ongeldige groottelimiet")


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("Bronverzoek duurde te lang")
    return remaining


def fetch_public_https(url, max_bytes, timeout, user_agent, max_redirects=3, return_final_url=False):
    """Fetch bounded bytes via HTTPS with public DNS and a pinned TCP peer.

    A cancellation timer interrupts TCP/TLS/header/body I/O at the deadline.
    Socket operations also use the remaining timeout budget. System DNS resolution
    uses the platform resolver, whose own timeout can exceed this budget; a
    delayed resolution is rejected before connecting. HTTP headers are bounded
    by http.client's line/count limits.
    """
    _positive_size(max_bytes)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Ongeldige timeout")
    if isinstance(max_redirects, bool) or not isinstance(max_redirects, int) or max_redirects < 0:
        raise ValueError("Ongeldige redirectlimiet")
    if not isinstance(user_agent, str) or not user_agent or re.search(r"[\x00-\x1f\x7f-\x9f]", user_agent):
        raise ValueError("Ongeldige User-Agent")
    try:
        user_agent.encode("latin-1")
    except UnicodeError:
        raise ValueError("Ongeldige User-Agent") from None
    deadline = time.monotonic() + timeout
    current_url = url
    for redirects in range(max_redirects + 1):
        parsed = _parse_https_url(current_url)
        address = _resolve_public(parsed.hostname, parsed.port)
        connection = _PinnedHTTPSConnection(parsed.hostname, parsed.port, address, _remaining(deadline))
        response = None
        timer = threading.Timer(_remaining(deadline), connection.abort)
        timer.daemon = True
        timer.start()
        try:
            connection.request("GET", parsed.target, headers={
                "User-Agent": user_agent, "Accept-Encoding": "identity", "Connection": "close",
            })
            stream = connection.sock
            stream.settimeout(_remaining(deadline))
            response = connection.getresponse()
            if response.status in _REDIRECTS:
                location = response.getheader("Location")
                if redirects >= max_redirects:
                    raise ValueError("Te veel bronredirects")
                if not isinstance(location, str) or not location or _FORBIDDEN_URL_CHARS.search(location) or any(c.isspace() for c in location):
                    raise ValueError("Ongeldige bronredirect")
                # URL parsing is repeated before DNS resolution on the next hop.
                current_url = urljoin(current_url, location)
                _parse_https_url(current_url)
                continue
            if not 200 <= response.status < 300:
                raise ValueError("Bronserver gaf HTTP-status " + str(response.status))
            length = response.getheader("Content-Length")
            if length is not None:
                if not re.fullmatch(r"[0-9]+", length.strip()):
                    raise ValueError("Ongeldige brongrootte")
                if int(length) > max_bytes:
                    raise ValueError("Bronrespons is te groot")
            chunks = []
            received = 0
            while not response.isclosed():
                stream.settimeout(_remaining(deadline))
                chunk = response.read1(min(64 * 1024, max_bytes + 1 - received))
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise ValueError("Bronrespons is te groot")
                chunks.append(chunk)
            if length is not None and received != int(length):
                raise ValueError("Onvolledige bronrespons")
            _remaining(deadline)
            body = b"".join(chunks)
            return (body, current_url) if return_final_url else body
        except (OSError, http.client.HTTPException):
            raise ValueError("Bron kon niet veilig worden opgehaald") from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            connection.close()
    raise ValueError("Te veel bronredirects")


def parse_xml(raw, max_bytes):
    """Parse bounded UTF-8/ASCII XML without DTD or entity declarations."""
    _positive_size(max_bytes)
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise ValueError("XML geweigerd: ongeldige invoer of te groot")
    size = raw.nbytes if isinstance(raw, memoryview) else len(raw)
    if size > max_bytes:
        raise ValueError("XML geweigerd: ongeldige invoer of te groot")
    raw = bytes(raw)
    if b"\x00" in raw:
        # Reject UTF-16/32 and NULs before any XML parser sees the document.
        raise ValueError("XML geweigerd: alleen UTF-8 of ASCII")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("XML geweigerd: alleen UTF-8 of ASCII") from None
    declaration = _XML_DECLARATION.match(text)
    if declaration:
        encoding = _XML_ENCODING.search(declaration.group())
        if encoding:
            name = encoding.group(2).lower()
            if name not in ("utf-8", "utf8", "ascii", "us-ascii") or (name in ("ascii", "us-ascii") and not text.isascii()):
                raise ValueError("XML geweigerd: alleen UTF-8 of ASCII")
    if _XML_DECLARATIONS.search(text):
        raise ValueError("XML geweigerd: DTD/entities")
    try:
        return ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise ValueError("Ongeldige XML") from None
