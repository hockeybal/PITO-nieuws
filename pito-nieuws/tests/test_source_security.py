"""Offline trust-boundary tests; sockets, DNS and HTTP responses are fakes."""

import http.client
import io
import os
from pathlib import Path
import socket
import ssl
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import source_security as security


def answer(ip="8.8.8.8", port=443):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    address = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", address)


class FakeSocket:
    def __init__(self):
        self.timeouts = []
        self.peers = []
        self.closed = False
        self.shutdowns = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def setsockopt(self, *args):
        pass

    def connect(self, peer):
        self.peers.append(peer)

    def close(self):
        self.closed = True

    def shutdown(self, how):
        self.shutdowns.append(how)

    def do_handshake(self):
        pass


class FakeResponse:
    def __init__(self, body=b"fixture", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}
        self.read_sizes = []
        self.closed = False

    def getheader(self, name):
        return self.headers.get(name)

    def read1(self, size):
        self.read_sizes.append(size)
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self):
        self.closed = True

    def isclosed(self):
        return self.closed


class NetworkFixture:
    def __init__(self, responses, *, dns=None, detach_socket=False):
        self.responses = iter(responses)
        self.dns = dns or [answer()]
        self.detach_socket = detach_socket
        self.connections = []

    def connection(self, host, port, address, timeout):
        response = next(self.responses)
        connection = Mock()
        connection.host = host
        connection.port = port
        connection.address = address
        connection.timeout = timeout
        connection.sock = FakeSocket()
        connection.original_socket = connection.sock

        def getresponse():
            if self.detach_socket:
                # http.client does this for Connection: close responses.
                connection.sock = None
            return response

        connection.getresponse.side_effect = getresponse
        self.connections.append(connection)
        return connection

    def fetch(self, url="https://example.org/feed", **kwargs):
        defaults = dict(max_bytes=100, timeout=10, user_agent="PITO-tests/1.0")
        defaults.update(kwargs)
        with patch.object(security.socket, "getaddrinfo", return_value=self.dns), patch.object(security, "_PinnedHTTPSConnection", side_effect=self.connection):
            return security.fetch_public_https(url, **defaults)


class URLTests(unittest.TestCase):
    def test_https_links_are_syntactic_and_do_not_resolve(self):
        with patch.object(security.socket, "getaddrinfo", side_effect=AssertionError("network")):
            for url in ("https://example.org", "HTTPS://Example.org/a?b=c#part", "https://example.org:8443/a", "https://[2606:4700:4700::1111]/", "https://münchen.example/nieuws"):
                with self.subTest(url=url):
                    self.assertTrue(security.safe_external_url(url))

    def test_invalid_links_are_rejected_before_dns(self):
        urls = (None, b"https://example.org", "", "http://example.org", "javascript:alert(1)", "//example.org", "https:///path", "https://u:p@example.org", "https://@example.org", "https://example.org:0", "https://example.org:65536", "https://example.org:", "https://[::1", "https://[v1.foo]/", "https://[2606:4700:4700::1111]suffix", "https://example.org\n/path", "https://example.org/\r", " https://example.org", "https://example.org/a b", "https://example.org/\x7f", "https://example.org/\x85", "https://exa\\mple.org", "https://example.org\\path", "https://%31%32%37.0.0.1", "https://[fe80::1%25eth0]/", "https://-example.org", "https://example..org")
        with patch.object(security.socket, "getaddrinfo", side_effect=AssertionError("network")):
            for url in urls:
                with self.subTest(url=url):
                    self.assertFalse(security.safe_external_url(url))
                    with self.assertRaises(ValueError):
                        security.fetch_public_https(url, 100, 10, "test")

    def test_unicode_target_is_encoded_and_fragment_is_omitted(self):
        parsed = security._parse_https_url("https://münchen.example/één?q=é#part")
        self.assertEqual(parsed.hostname, "xn--mnchen-3ya.example")
        self.assertEqual(parsed.target, "/%C3%A9%C3%A9n?q=%C3%A9")


class DNSAndPinningTests(unittest.TestCase):
    def test_nonpublic_addresses_are_rejected(self):
        for ip in ("127.0.0.1", "10.1.2.3", "172.16.1.2", "192.168.1.2", "169.254.169.254", "0.0.0.0", "100.64.0.1", "198.18.0.1", "203.0.113.1", "224.0.0.1", "240.0.0.1", "::", "::1", "fc00::1", "fe80::1", "fec0::1", "ff02::1", "::ffff:127.0.0.1"):
            with self.subTest(ip=ip), patch.object(security.socket, "getaddrinfo", return_value=[answer(ip)]):
                with self.assertRaises(ValueError):
                    security._resolve_public("example.org", 443)

    def test_one_private_answer_rejects_all_answers(self):
        fixture = NetworkFixture([FakeResponse()], dns=[answer(), answer("127.0.0.1")])
        with self.assertRaises(ValueError):
            fixture.fetch()
        self.assertFalse(fixture.connections)

    def test_public_ipv4_and_ipv6_are_allowed(self):
        for ip in ("8.8.8.8", "2606:4700:4700::1111"):
            with self.subTest(ip=ip), patch.object(security.socket, "getaddrinfo", return_value=[answer(ip, 8443)]):
                address = security._resolve_public("example.org", 8443)
                self.assertEqual(address.sockaddr[0], ip)
                self.assertEqual(address.sockaddr[1], 8443)

    def test_empty_and_failed_dns_are_safe_errors(self):
        for result in ([], None):
            options = dict(return_value=result) if result == [] else dict(side_effect=socket.gaierror("private resolver detail"))
            with self.subTest(result=result), patch.object(security.socket, "getaddrinfo", **options):
                with self.assertRaises(ValueError) as caught:
                    security._resolve_public("example.org", 443)
                self.assertNotIn("private resolver detail", str(caught.exception))

    def test_pinned_connect_uses_numeric_peer_with_original_tls_hostname(self):
        for ip in ("8.8.8.8", "2606:4700:4700::1111"):
            stream = FakeSocket()
            context = Mock()
            context.wrap_socket.return_value = stream
            with self.subTest(ip=ip), patch.object(security.socket, "getaddrinfo", return_value=[answer(ip)]) as dns, patch.object(security.socket, "socket", return_value=stream) as sockets, patch.object(security.ssl, "create_default_context", return_value=context):
                address = security._resolve_public("example.org", 443)
                # A second lookup now yields a private peer. It must never occur.
                dns.return_value = [answer("127.0.0.1")]
                connection = security._PinnedHTTPSConnection("example.org", 443, address, 4)
                connection.connect()
                self.assertEqual(stream.peers, [address.sockaddr])
                self.assertEqual(dns.call_count, 1)
                context.wrap_socket.assert_called_once_with(stream, server_hostname="example.org", do_handshake_on_connect=False)
                sockets.assert_called_once_with(address.family, socket.SOCK_STREAM, socket.IPPROTO_TCP)

    def test_real_default_tls_context_verifies_certificate_and_hostname(self):
        address = security._Address(socket.AF_INET, ("8.8.8.8", 443))
        connection = security._PinnedHTTPSConnection("example.org", 443, address, 1)
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)
        connection.close()

    def test_failed_pinned_connect_closes_socket(self):
        stream = FakeSocket()
        stream.connect = Mock(side_effect=TimeoutError("private detail"))
        address = security._Address(socket.AF_INET, ("8.8.8.8", 443))
        connection = security._PinnedHTTPSConnection("example.org", 443, address, 1)
        with patch.object(security.socket, "socket", return_value=stream):
            with self.assertRaises(TimeoutError):
                connection._connect_pinned(("example.org", 443), 1)
        self.assertTrue(stream.closed)

    def test_deadline_aborts_tcp_and_prevents_a_later_connect(self):
        stream = FakeSocket()
        address = security._Address(socket.AF_INET, ("8.8.8.8", 443))
        connection = security._PinnedHTTPSConnection("example.org", 443, address, 1)
        with patch.object(security.socket, "socket", return_value=stream):
            connection._connect_pinned(("example.org", 443), 1)
            connection.abort()
            self.assertEqual(stream.shutdowns, [socket.SHUT_RDWR])
            self.assertTrue(stream.closed)
            with self.assertRaises(TimeoutError):
                connection._connect_pinned(("example.org", 443), 1)

    def test_deadline_keeps_socket_after_http_client_detaches_connection(self):
        stream = FakeSocket()
        address = security._Address(socket.AF_INET, ("8.8.8.8", 443))
        connection = security._PinnedHTTPSConnection("example.org", 443, address, 1)
        with patch.object(security.socket, "socket", return_value=stream):
            connection.sock = connection._connect_pinned(("example.org", 443), 1)
            connection.close()
            self.assertIsNone(connection.sock)
            self.assertIs(connection._active_socket, stream)
            connection.abort()
            self.assertEqual(stream.shutdowns, [socket.SHUT_RDWR])

    def test_deadline_has_tls_socket_reference_during_handshake(self):
        raw = FakeSocket()
        tls = FakeSocket()
        context = Mock()
        context.wrap_socket.return_value = tls
        address = security._Address(socket.AF_INET, ("8.8.8.8", 443))
        with patch.object(security.socket, "socket", return_value=raw), patch.object(security.ssl, "create_default_context", return_value=context):
            connection = security._PinnedHTTPSConnection("example.org", 443, address, 1)

            def handshake():
                self.assertIs(connection._active_socket, tls)
                connection.abort()
                raise TimeoutError("interrupted handshake")

            tls.do_handshake = handshake
            with self.assertRaises(TimeoutError):
                connection.connect()
            self.assertEqual(tls.shutdowns, [socket.SHUT_RDWR])
            self.assertTrue(tls.closed)


class FetchTests(unittest.TestCase):
    def test_deadline_timer_is_armed_and_canceled_on_success_and_error(self):
        for status in (200, 503):
            fixture = NetworkFixture([FakeResponse(status=status)])
            timer = Mock()
            with self.subTest(status=status), patch.object(security.threading, "Timer", return_value=timer) as timer_factory:
                if status == 200:
                    fixture.fetch()
                else:
                    with self.assertRaises(ValueError):
                        fixture.fetch()
                connection = fixture.connections[0]
                delay, callback = timer_factory.call_args.args
                self.assertTrue(0 < delay <= 10)
                self.assertEqual(callback, connection.abort)
                self.assertTrue(timer.daemon)
                timer.start.assert_called_once()
                timer.cancel.assert_called_once()

    def test_real_http_response_closes_at_content_length_without_later_socket_io(self):
        class WireSocket(FakeSocket):
            def __init__(self):
                super().__init__()
                self.file = io.BytesIO(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 7\r\n\r\npayload")

            def makefile(self, *args):
                return self.file

            def settimeout(self, value):
                if self.file.closed:
                    raise OSError("socket file already closed")
                super().settimeout(value)

        stream = WireSocket()
        connection = Mock(sock=stream)

        def getresponse():
            response = http.client.HTTPResponse(stream)
            response.begin()
            connection.sock = None
            return response

        connection.getresponse.side_effect = getresponse
        with patch.object(security.socket, "getaddrinfo", return_value=[answer()]), patch.object(security, "_PinnedHTTPSConnection", return_value=connection):
            self.assertEqual(security.fetch_public_https("https://example.org", 100, 10, "test"), b"payload")
        self.assertTrue(stream.file.closed)

    def test_bytes_and_connection_close_with_identity_encoding(self):
        response = FakeResponse(b"payload", headers={"Content-Length": "7"})
        fixture = NetworkFixture([response], detach_socket=True)
        self.assertEqual(fixture.fetch(), b"payload")
        connection = fixture.connections[0]
        connection.request.assert_called_once_with("GET", "/feed", headers={"User-Agent": "PITO-tests/1.0", "Accept-Encoding": "identity", "Connection": "close"})
        connection.close.assert_called_once()
        self.assertTrue(response.closed)
        self.assertTrue(all(0 < timeout <= 10 for timeout in connection.original_socket.timeouts))

    def test_environment_proxy_is_not_used(self):
        with patch.dict(os.environ, {"https_proxy": "http://127.0.0.1:8080", "HTTPS_PROXY": "http://127.0.0.1:8080", "ALL_PROXY": "http://127.0.0.1:8080"}):
            fixture = NetworkFixture([FakeResponse()])
            self.assertEqual(fixture.fetch(), b"fixture")
            self.assertEqual(fixture.connections[0].address.sockaddr, ("8.8.8.8", 443))

    def test_relative_redirect_has_new_dns_and_pinning_without_reading_body(self):
        redirect = FakeResponse(b"must not read", 302, {"Location": "../final?q=1"})
        fixture = NetworkFixture([redirect, FakeResponse(b"final")])
        with patch.object(security.socket, "getaddrinfo", side_effect=[[answer()], [answer("1.1.1.1")]]) as dns, patch.object(security, "_PinnedHTTPSConnection", side_effect=fixture.connection):
            data = security.fetch_public_https("https://example.org/path/feed", 100, 10, "test", return_final_url=True)
        self.assertEqual(data, (b"final", "https://example.org/final?q=1"))
        self.assertEqual(dns.call_count, 2)
        self.assertEqual(fixture.connections[1].address.sockaddr, ("1.1.1.1", 443))
        self.assertFalse(redirect.read_sizes)
        self.assertTrue(redirect.closed)

    def test_public_cross_host_redirect_is_allowed_and_revalidated(self):
        fixture = NetworkFixture([FakeResponse(status=307, headers={"Location": "https://other.example/feed"}), FakeResponse(b"ok")])
        self.assertEqual(fixture.fetch(), b"ok")
        self.assertEqual([c.host for c in fixture.connections], ["example.org", "other.example"])

    def test_private_redirect_is_rejected_before_second_connect(self):
        redirect = FakeResponse(status=302, headers={"Location": "https://other.example/feed"})
        fixture = NetworkFixture([redirect, FakeResponse()])
        with patch.object(security.socket, "getaddrinfo", side_effect=[[answer()], [answer("169.254.169.254")]]), patch.object(security, "_PinnedHTTPSConnection", side_effect=fixture.connection):
            with self.assertRaises(ValueError):
                security.fetch_public_https("https://example.org", 100, 10, "test")
        self.assertEqual(len(fixture.connections), 1)
        self.assertFalse(redirect.read_sizes)

    def test_unsafe_or_missing_redirects_are_rejected(self):
        for target in (None, "", "http://example.org/feed", "https://u:p@example.org", "https://other.example/\n", "\thttps://other.example", "https://example.org/a b"):
            with self.subTest(target=target):
                fixture = NetworkFixture([FakeResponse(status=302, headers={"Location": target})])
                with self.assertRaises(ValueError):
                    fixture.fetch()
                self.assertEqual(len(fixture.connections), 1)

    def test_redirect_limit_is_enforced_without_reading_bodies(self):
        responses = [FakeResponse(status=301, headers={"Location": "/next"}) for _ in range(2)]
        fixture = NetworkFixture(responses)
        with self.assertRaisesRegex(ValueError, "redirects"):
            fixture.fetch(max_redirects=1)
        self.assertEqual(len(fixture.connections), 2)
        self.assertTrue(all(not response.read_sizes for response in responses))

    def test_zero_redirect_limit_rejects_first_redirect(self):
        fixture = NetworkFixture([FakeResponse(status=308, headers={"Location": "/next"})])
        with self.assertRaises(ValueError):
            fixture.fetch(max_redirects=0)
        self.assertEqual(len(fixture.connections), 1)

    def test_error_status_has_safe_value_error_and_no_body_read(self):
        response = FakeResponse(b"secret detail", 503)
        fixture = NetworkFixture([response])
        with self.assertRaisesRegex(ValueError, "503") as caught:
            fixture.fetch()
        self.assertNotIn("secret", str(caught.exception))
        self.assertFalse(response.read_sizes)

    def test_declared_oversize_is_rejected_without_body_read(self):
        response = FakeResponse(headers={"Content-Length": "101"})
        fixture = NetworkFixture([response])
        with self.assertRaises(ValueError):
            fixture.fetch(max_bytes=100)
        self.assertFalse(response.read_sizes)

    def test_undeclared_oversize_reads_at_most_limit_plus_one(self):
        response = FakeResponse(b"x" * 200)
        fixture = NetworkFixture([response])
        with self.assertRaises(ValueError):
            fixture.fetch(max_bytes=100)
        self.assertEqual(response.read_sizes, [101])
        self.assertEqual(len(response.body), 99)

    def test_exact_limit_is_accepted(self):
        fixture = NetworkFixture([FakeResponse(b"x" * 100)])
        self.assertEqual(fixture.fetch(max_bytes=100), b"x" * 100)

    def test_invalid_and_incomplete_lengths_are_rejected(self):
        for length in ("-1", "wat", "7,7", "10"):
            with self.subTest(length=length):
                fixture = NetworkFixture([FakeResponse(b"short", headers={"Content-Length": length})])
                with self.assertRaises(ValueError):
                    fixture.fetch()

    def test_network_and_http_exceptions_are_safe_and_close(self):
        for error in (TimeoutError("secret detail"), ssl.SSLError("secret detail"), http.client.BadStatusLine("secret detail")):
            fixture = NetworkFixture([FakeResponse()])
            with self.subTest(error=type(error).__name__), patch.object(security.socket, "getaddrinfo", return_value=[answer()]), patch.object(security, "_PinnedHTTPSConnection", side_effect=fixture.connection):
                def fail(*args, **kwargs):
                    connection = fixture.connection(*args, **kwargs)
                    connection.request.side_effect = error
                    return connection
                with patch.object(security, "_PinnedHTTPSConnection", side_effect=fail):
                    with self.assertRaises(ValueError) as caught:
                        security.fetch_public_https("https://example.org", 100, 10, "test")
                self.assertNotIn("secret", str(caught.exception))
                fixture.connections[0].close.assert_called_once()

    def test_invalid_limits_and_user_agent_fail_before_dns(self):
        cases = [dict(max_bytes=value) for value in (0, -1, 1.5, True)]
        cases += [dict(timeout=value) for value in (0, -1, float("nan"), float("inf"), True)]
        cases += [dict(max_redirects=value) for value in (-1, 1.5, True)]
        cases += [dict(user_agent=value) for value in ("", "bad\r\nHost: local", "bad\x00", "é☃")]
        with patch.object(security.socket, "getaddrinfo", side_effect=AssertionError("network")):
            for options in cases:
                args = dict(max_bytes=100, timeout=10, user_agent="test")
                args.update(options)
                with self.subTest(options=options), self.assertRaises(ValueError):
                    security.fetch_public_https("https://example.org", **args)

    def test_expired_dns_budget_prevents_connect(self):
        with patch.object(security.time, "monotonic", side_effect=[0, 11]), patch.object(security.socket, "getaddrinfo", return_value=[answer()]), patch.object(security, "_PinnedHTTPSConnection") as factory:
            with self.assertRaises(ValueError):
                security.fetch_public_https("https://example.org", 100, 10, "test")
            factory.assert_not_called()

    def test_eof_after_deadline_cannot_be_reported_as_success(self):
        fixture = NetworkFixture([FakeResponse(b"")])
        with patch.object(security.time, "monotonic", side_effect=[0, 0, 0, 0, 0, 11]):
            with self.assertRaisesRegex(ValueError, "te lang"):
                fixture.fetch()


class XMLTests(unittest.TestCase):
    def test_ascii_utf8_and_utf8_bom_parse(self):
        for raw in (b"<rss><item>Test &amp; text</item></rss>", '<?xml version="1.0" encoding="UTF-8"?><rss>één</rss>'.encode(), b"\xef\xbb\xbf<rss/>", b'<?xml version="1.0" encoding="US-ASCII"?><rss/>'):
            with self.subTest(raw=raw):
                self.assertEqual(security.parse_xml(raw, 1000).tag, "rss")

    def test_dtd_entities_and_encoded_forms_never_reach_parser(self):
        xml = '<!DOCTYPE rss [<!ENTITY bomb "boom">]><rss>&bomb;</rss>'
        cases = [xml.encode("utf-8"), b"\xef\xbb\xbf" + xml.encode("utf-8"), xml.encode("utf-16"), xml.encode("utf-16-le"), xml.encode("utf-16-be"), xml.encode("utf-32"), xml.encode("utf-32-le"), xml.encode("utf-32-be"), b'<!ENTITY x SYSTEM "file:///etc/passwd"><rss/>', b'<!doctype rss><rss/>']
        with patch.object(security.ET, "fromstring", side_effect=AssertionError("unsafe parser input")) as parser:
            for raw in cases:
                with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                    security.parse_xml(raw, 1000)
            parser.assert_not_called()

    def test_unsupported_encoding_and_nuls_never_reach_parser(self):
        cases = [b'<?xml version="1.0" encoding="UTF-16"?><rss/>', b'<?xml version="1.0" encoding="UTF-7"?><rss/>', b'<?xml version="1.0" encoding="ISO-8859-1"?><rss/>', b"<rss>\xe9</rss>", b"<rss>\x00</rss>", b"\xff\xfe", b"\xfe\xff", '<rss/>'.encode("utf-32")]
        with patch.object(security.ET, "fromstring", side_effect=AssertionError("unsafe parser input")) as parser:
            for raw in cases:
                with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                    security.parse_xml(raw, 1000)
            parser.assert_not_called()

    def test_ascii_declaration_with_nonascii_content_is_rejected(self):
        with self.assertRaises(ValueError):
            security.parse_xml('<?xml version="1.0" encoding="ASCII"?><rss>é</rss>'.encode(), 1000)

    def test_oversize_and_invalid_inputs_fail_before_parser(self):
        cases = [(b"<rss/>", 5), ("<rss/>", 100), (None, 100), (memoryview(b"abcdefgh").cast("I"), 4), (b"<rss/>", 0)]
        with patch.object(security.ET, "fromstring", side_effect=AssertionError("oversize parser input")) as parser:
            for raw, limit in cases:
                with self.subTest(raw=raw, limit=limit), self.assertRaises(ValueError):
                    security.parse_xml(raw, limit)
            parser.assert_not_called()

    def test_exact_size_and_bytes_like_inputs_are_accepted(self):
        for raw in (b"<rss/>", bytearray(b"<rss/>"), memoryview(b"<rss/>")):
            with self.subTest(raw=type(raw).__name__):
                self.assertEqual(security.parse_xml(raw, 6).tag, "rss")

    def test_malformed_xml_raises_safe_value_error(self):
        with self.assertRaisesRegex(ValueError, "Ongeldige XML"):
            security.parse_xml(b"<rss>", 100)


if __name__ == "__main__":
    unittest.main()
