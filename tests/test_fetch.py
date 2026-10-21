"""Tests for scripts/fetch, the agent's only way to make a web request.

fetch exists to bound where a request can go: only an origin listed
in scripts/fetch-origins (next to the script) is contacted, every
redirect hop is checked against the same list, and no curl option
beyond -I reaches curl.  Each test copies the real script next to an
origins file naming a loopback fixture server.

A refusal is checked three ways, since curl failing on a bad URL by
itself looks just like fetch refusing it: stderr must carry one of
fetch's own refusal messages; no fixture server may see a connection
at all (not just a parsed request); and the proxy every scheme is
pointed at is itself a recording server, so a request for any host
other than 127.0.0.1 shows up there instead of vanishing.
"""

import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "scripts", "fetch")

# What fetch prints when it refuses, as opposed to a curl or HTTP
# failure ("Cannot fetch", "HTTP 404 from").
REFUSALS = (b"Not an http(s) URL", b"Malformed host", b"Origin not listed",
            b"Usage:", b"Cannot read")


class Server:
    """A loopback HTTP server with fixed pages and redirects.

    `pages` maps a path to a body, `redirects` a path to a
    (status, Location) pair; anything else answers 404.  Every
    accepted connection is counted in `connections`, and every request
    -- whatever its method, CONNECT included -- is appended to
    `requests` as (method, path) and its headers to `headers`, before
    any dispatch on the method.
    """

    def __init__(self):
        self.pages = {}
        self.redirects = {}
        self.requests = []
        self.headers = []
        self.connections = 0
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def parse_request(self):
                ok = super().parse_request()
                if ok:
                    server.requests.append((self.command, self.path))
                    server.headers.append(dict(self.headers))
                return ok

            def answer(self, body):
                if self.path in server.redirects:
                    status, location = server.redirects[self.path]
                    self.send_response(status)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path not in server.pages:
                    self.send_error(404)
                    return
                data = server.pages[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Fixture", "yes")
                self.end_headers()
                if body:
                    self.wfile.write(data)

            def do_GET(self):
                self.answer(True)

            def do_HEAD(self):
                self.answer(False)

            def log_message(self, *args):
                pass

        class HTTPServer(http.server.ThreadingHTTPServer):
            def verify_request(self, request, client_address):
                server.connections += 1
                return True

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True)
        self.thread.start()
        self.closed = False

    @property
    def port(self):
        return self.httpd.server_address[1]

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.port

    def url(self, path):
        return self.origin + path

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fetch-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.scripts = os.path.join(self.tmp, "scripts")
        os.makedirs(self.scripts)
        self.fetch = os.path.join(self.scripts, "fetch")
        shutil.copy2(SCRIPT, self.fetch)

        self.ok = Server()
        self.addCleanup(self.ok.close)
        # A second origin that is never listed unless a test says so:
        # reaching it is the failure every refusal test guards against.
        self.evil = Server()
        self.addCleanup(self.evil.close)
        # Every scheme's proxy: a request for any host but 127.0.0.1
        # (a DNS name, a lookalike) lands here instead of failing in a
        # way that cannot be told from a refusal.
        self.proxy = Server()
        self.addCleanup(self.proxy.close)

        self.ok.pages["/page"] = b"allowed body\n"
        self.evil.pages["/page"] = b"evil body\n"
        self.origins("# comment line\n\n%s\n" % self.ok.origin)

        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.env = dict(
            os.environ,
            HOME=self.home,
            XDG_CONFIG_HOME=self.home,
            CURL_HOME=self.home,
            http_proxy=self.proxy.origin,
            https_proxy=self.proxy.origin,
            HTTPS_PROXY=self.proxy.origin,
            ALL_PROXY=self.proxy.origin,
            no_proxy="127.0.0.1",
            NO_PROXY="127.0.0.1",
        )

    def origins(self, text):
        with open(os.path.join(self.scripts, "fetch-origins"), "w") as f:
            f.write(text)

    def run_fetch(self, *args):
        return subprocess.run(
            [self.fetch] + list(args),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=self.env,
            timeout=60,
        )

    def assert_untouched(self, *servers):
        for server in servers or (self.ok, self.evil, self.proxy):
            self.assertEqual(server.connections, 0, server.requests)

    def assert_refused(self, *args):
        res = self.run_fetch(*args)
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertTrue(any(r in res.stderr for r in REFUSALS), res)
        self.assert_untouched()
        return res

    # -- what passes -------------------------------------------------

    def test_listed_origin_body_on_stdout(self):
        res = self.run_fetch(self.ok.url("/page"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"allowed body\n")
        self.assertEqual(self.ok.requests, [("GET", "/page")])
        self.assert_untouched(self.evil, self.proxy)

    def test_binary_body_passes_through_unchanged(self):
        data = bytes(range(256)) * 4
        self.ok.pages["/blob.gz"] = data
        res = self.run_fetch(self.ok.url("/blob.gz"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, data)

    def test_query_string_allowed(self):
        self.ok.pages["/q?package=linux&s=sid"] = b"madison\n"
        res = self.run_fetch(self.ok.url("/q?package=linux&s=sid"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"madison\n")

    def test_bare_origin_without_path(self):
        self.ok.pages["/"] = b"root\n"
        res = self.run_fetch(self.ok.origin)
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"root\n")

    def test_fragment_and_query_cannot_move_the_host(self):
        # Everything after # or ? is not the authority: the listed
        # host gets the request and the "@host" never does.
        self.ok.pages["/"] = b"root\n"
        for sep in ("#", "?", "/"):
            url = "%s%s@127.0.0.1:%d/page" % (self.ok.origin, sep,
                                              self.evil.port)
            self.run_fetch(url)
        self.assertEqual(len(self.ok.requests), 3)
        self.assert_untouched(self.evil, self.proxy)

    def test_head_prints_headers_not_body(self):
        res = self.run_fetch("-I", self.ok.url("/page"))
        self.assertEqual(res.returncode, 0, res)
        self.assertIn(b"200", res.stdout.splitlines()[0])
        self.assertIn(b"X-Fixture: yes", res.stdout)
        self.assertEqual(self.ok.requests, [("HEAD", "/page")])

    def test_redirect_within_listed_origin_followed(self):
        for status in (301, 302, 303, 307, 308):
            self.ok.requests.clear()
            self.ok.redirects["/old"] = (status, "/page")
            res = self.run_fetch(self.ok.url("/old"))
            self.assertEqual(res.returncode, 0, (status, res))
            self.assertEqual(res.stdout, b"allowed body\n")
            self.assertEqual(self.ok.requests,
                             [("GET", "/old"), ("GET", "/page")])

    def test_redirect_relative_to_query(self):
        self.ok.pages["/page?x"] = b"query page\n"
        self.ok.redirects["/page?y"] = (302, "?x")
        res = self.run_fetch(self.ok.url("/page?y"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"query page\n")

    def test_redirect_to_other_listed_origin_followed(self):
        self.origins("%s\n%s\n" % (self.ok.origin, self.evil.origin))
        self.ok.redirects["/old"] = (302, self.evil.url("/page"))
        res = self.run_fetch(self.ok.url("/old"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"evil body\n")

    def test_head_follows_redirect(self):
        self.ok.redirects["/old"] = (302, "/page")
        res = self.run_fetch("-I", self.ok.url("/old"))
        self.assertEqual(res.returncode, 0, res)
        self.assertIn(b"X-Fixture: yes", res.stdout)
        self.assertEqual(self.ok.requests,
                         [("HEAD", "/old"), ("HEAD", "/page")])

    def test_curlrc_ignored(self):
        with open(os.path.join(self.home, ".curlrc"), "w") as f:
            f.write('header = "X-Leak: curlrc"\n')
        res = self.run_fetch(self.ok.url("/page"))
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("X-Leak", self.ok.headers[0])

    def test_no_url_globbing(self):
        # curl would expand {a,b} into two requests; fetch makes one,
        # for the literal path.
        self.ok.pages["/{a,b}"] = b"literal\n"
        res = self.run_fetch(self.ok.url("/{a,b}"))
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"literal\n")
        self.assertEqual(self.ok.requests, [("GET", "/{a,b}")])

    # -- origin checks -----------------------------------------------

    def test_unlisted_origin_refused(self):
        self.assert_refused(self.evil.url("/page"))

    def test_commented_origin_not_listed(self):
        self.origins("# %s\n" % self.ok.origin)
        self.assert_refused(self.ok.url("/page"))

    def test_origin_entry_is_not_a_prefix_or_pattern(self):
        # A listed origin with a path never matches, and the dots in
        # a listed host are not regex wildcards.
        self.origins("%s/\n" % self.ok.origin)
        self.assert_refused(self.ok.url("/page"))
        self.origins("http://127a0a0a1:%d\n" % self.ok.port)
        self.assert_refused(self.ok.url("/page"))
        self.origins("http://127.0.0.1:%d\n" % self.ok.port)
        self.assert_refused("http://127a0a0a1:%d/page" % self.ok.port)

    def test_scheme_must_match_listed_origin(self):
        # Listed as http://, so https:// is a different origin.
        self.assert_refused(self.ok.url("/page").replace("http:", "https:"))

    def test_port_must_match_listed_origin(self):
        self.assert_refused(self.ok.url("/page").replace(
            str(self.ok.port), str(self.ok.port) + "0"))

    def test_host_suffix_and_prefix_tricks_refused(self):
        port = self.ok.port
        self.assert_refused("http://127.0.0.1.:%d/page" % port)
        self.assert_refused("http://x127.0.0.1:%d/page" % port)
        self.assert_refused("http://127.0.0.1:%d.evil.invalid/page" % port)

    def test_userinfo_refused(self):
        # Both readings of an @ must fail: credentials for the listed
        # host, or the listed host as credentials for another one.
        self.assert_refused("http://user@127.0.0.1:%d/page" % self.ok.port)
        self.assert_refused("http://127.0.0.1:%d@127.0.0.1:%d/page"
                            % (self.ok.port, self.evil.port))

    def test_backslash_and_encoding_in_authority_refused(self):
        port = self.ok.port
        self.assert_refused("http://127.0.0.1:%d\\@evil.invalid/page" % port)
        self.assert_refused("http://127.0.0.%%31:%d/page" % port)

    def test_uppercase_scheme_refused(self):
        self.assert_refused(self.ok.url("/page").replace("http:", "HTTP:"))

    def test_other_schemes_refused(self):
        secret = os.path.join(self.tmp, "secret")
        with open(secret, "w") as f:
            f.write("do not read\n")
        res = self.assert_refused("file://" + secret)
        self.assertNotIn(b"do not read", res.stderr)
        self.assert_refused("ftp://127.0.0.1:%d/page" % self.ok.port)
        self.assert_refused("dict://127.0.0.1:%d/" % self.ok.port)
        self.assert_refused("127.0.0.1:%d/page" % self.ok.port)
        self.assert_refused("//127.0.0.1:%d/page" % self.ok.port)

    def test_crlf_origins_file_fails_closed(self):
        self.origins("%s\r\n" % self.ok.origin)
        self.assert_refused(self.ok.url("/page"))

    def test_missing_origins_file_fails_closed(self):
        os.unlink(os.path.join(self.scripts, "fetch-origins"))
        self.assert_refused(self.ok.url("/page"))

    # -- redirect checks ---------------------------------------------

    def assert_redirect_refused(self, location, *opts):
        self.ok.redirects["/old"] = (302, location)
        res = self.run_fetch(*(list(opts) + [self.ok.url("/old")]))
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertTrue(any(r in res.stderr for r in REFUSALS), res)
        method = "HEAD" if opts else "GET"
        self.assertEqual(self.ok.requests, [(method, "/old")])
        self.assert_untouched(self.evil, self.proxy)

    def test_redirect_to_unlisted_origin_refused(self):
        self.assert_redirect_refused(self.evil.url("/page"))

    def test_head_redirect_to_unlisted_origin_refused(self):
        self.assert_redirect_refused(self.evil.url("/page"), "-I")

    def test_protocol_relative_redirect_refused(self):
        self.assert_redirect_refused("//127.0.0.1:%d/page" % self.evil.port)

    def test_uppercase_redirect_to_unlisted_origin_refused(self):
        self.assert_redirect_refused("HTTP://127.0.0.1:%d/page"
                                     % self.evil.port)

    def test_userinfo_redirect_refused(self):
        self.assert_redirect_refused("http://127.0.0.1:%d@127.0.0.1:%d/page"
                                     % (self.ok.port, self.evil.port))

    def test_redirect_to_file_refused(self):
        self.assert_redirect_refused("file:///etc/passwd")

    def test_redirect_loop_bounded(self):
        self.ok.redirects["/loop"] = (302, "/loop")
        res = self.run_fetch(self.ok.url("/loop"))
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertIn(b"redirects", res.stderr)
        self.assertGreater(len(self.ok.requests), 1)
        self.assertLessEqual(len(self.ok.requests), 10)

    # -- argument checks ---------------------------------------------

    def test_curl_options_refused(self):
        out = os.path.join(self.tmp, "out")
        url = self.ok.url("/page")
        for args in (
            ["-o", out, url],
            [url, "-o", out],
            ["-d", "secret=1", url],
            [url, "-d", "secret=1"],
            ["-H", "X-Leak: secret", url],
            ["-K", os.path.join(self.tmp, "cfg"), url],
            ["--data-binary", "@" + SCRIPT, url],
            ["-T", SCRIPT, url],
            ["-X", "POST", url],
            ["-I", "-o", out, url],
            [url, "-I"],
        ):
            self.assert_refused(*args)
        self.assertFalse(os.path.exists(out))

    def test_exactly_one_url(self):
        self.assert_refused()
        self.assert_refused(self.ok.url("/page"), self.ok.url("/page"))
        self.assert_refused("-I")

    # -- failures ----------------------------------------------------

    def test_http_error_fails_without_body(self):
        res = self.run_fetch(self.ok.url("/missing"))
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertIn(b"404", res.stderr)

    def test_unreachable_origin_fails(self):
        url = self.ok.url("/page")
        self.ok.close()
        res = self.run_fetch(url)
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertIn(b"Cannot fetch", res.stderr)


if __name__ == "__main__":
    unittest.main()
