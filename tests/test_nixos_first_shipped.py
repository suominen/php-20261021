"""Tests for scripts/nixos-first-shipped.

The helper lists a channel's releases from the nix-releases bucket and
binary-searches a local nixpkgs clone for the first one containing a
commit.  The headless agent may run it with any arguments, so the
channel and commit it is handed are untrusted: a channel name once
reached a sed script verbatim, where GNU sed's `e` flag runs a shell
command.  Each test drives the real script with -b pointed at a
loopback fixture bucket and -r at a throwaway git repository, so no
test touches the network.
"""

import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "scripts", "nixos-first-shipped")

GIT_ENV = dict(
    os.environ,
    GIT_AUTHOR_NAME="Test",
    GIT_AUTHOR_EMAIL="test@example.invalid",
    GIT_COMMITTER_NAME="Test",
    GIT_COMMITTER_EMAIL="test@example.invalid",
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_NOSYSTEM="1",
    # A dead proxy, so a request that escapes the fixture bucket fails
    # instead of reaching a real server; loopback is exempt.
    http_proxy="http://127.0.0.1:9",
    https_proxy="http://127.0.0.1:9",
    HTTPS_PROXY="http://127.0.0.1:9",
    ALL_PROXY="http://127.0.0.1:9",
    no_proxy="127.0.0.1",
    NO_PROXY="127.0.0.1",
)


class Bucket:
    """A loopback stand-in for the S3 bucket's ListObjects API.

    `releases` maps a key prefix (`nixos/26.05/`) to a list of
    (release directory, LastModified date) pairs, oldest first.  A
    listing request answers with one CommonPrefixes entry per release,
    `page` at a time with IsTruncated/NextMarker; a request for
    `<prefix><dir>/git-revision` answers with that key's LastModified.
    Every request's decoded query is appended to `requests`.
    """

    def __init__(self, page=1000):
        self.releases = {}
        self.page = page
        self.requests = []
        bucket = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(self.path).query,
                    keep_blank_values=True)
                query = {k: v[0] for k, v in query.items()}
                bucket.requests.append(query)
                body = bucket.answer(query).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True)
        self.thread.start()

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def answer(self, query):
        prefix = query.get("prefix", "")
        if prefix.endswith("/git-revision"):
            for top, releases in self.releases.items():
                for name, date in releases:
                    if prefix == top + name + "/git-revision":
                        return ("<ListBucketResult><Contents><Key>%s</Key>"
                                "<LastModified>%sT12:00:00.000Z"
                                "</LastModified></Contents>"
                                "</ListBucketResult>" % (prefix, date))
            return "<ListBucketResult></ListBucketResult>"

        # S3 lists keys in lexicographic order, not release order.
        names = sorted(n for n, _ in self.releases.get(prefix, []))
        marker = query.get("marker", "")
        if marker:
            names = [n for n in names if prefix + n + "/" > marker]
        chunk, rest = names[:self.page], names[self.page:]
        out = ["<ListBucketResult><Prefix>%s</Prefix>" % prefix,
               "<IsTruncated>%s</IsTruncated>"
               % ("true" if rest else "false")]
        out += ["<CommonPrefixes><Prefix>%s%s/</Prefix></CommonPrefixes>"
                % (prefix, n) for n in chunk]
        if rest:
            out.append("<NextMarker>%s%s/</NextMarker>"
                       % (prefix, chunk[-1]))
        out.append("</ListBucketResult>")
        return "".join(out)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


class NixosFirstShippedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nixos-first-shipped-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = os.path.join(self.tmp, "nixpkgs")
        os.makedirs(self.repo)
        self.git("init", "-q", "-b", "master")
        self.commits = []
        # Eleven releases, so that lexicographic order (.10 before .2)
        # differs from release order and the script has to sort.
        for i in range(1, 12):
            self.git("commit", "-q", "--allow-empty", "-m", "c%d" % i)
            self.commits.append(self.git("rev-parse", "HEAD").strip())
        self.bucket = Bucket()
        self.addCleanup(self.bucket.close)
        # One release per commit, published a day apart.
        self.bucket.releases["nixos/26.05/"] = [
            ("nixos-26.05.%d.%s" % (i, sha[:12]), "2026-10-%02d" % i)
            for i, sha in enumerate(self.commits, 1)]

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", self.repo] + list(args),
            check=True, capture_output=True, text=True,
            env=GIT_ENV).stdout

    def run_script(self, channel, commit, bucket=None):
        argv = [SCRIPT]
        if bucket is not False:
            argv += ["-b", bucket or self.bucket.url]
        # HOME is the test's own directory, so no ~/.curlrc applies.
        return subprocess.run(
            argv + ["-r", self.repo, channel, commit],
            capture_output=True, text=True,
            env=dict(GIT_ENV, HOME=self.tmp), cwd=self.tmp, timeout=15)

    def assert_refused(self, result, message):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)
        self.assertEqual(self.bucket.requests, [])

    def release(self, n):
        """The line the script prints for release n (1-based)."""
        return ("nixos-26.05\tnixos-26.05.%d.%s\t2026-10-%02d\n"
                % (n, self.commits[n - 1][:12], n))

    def assert_found(self, result, n):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.release(n))
        # A warning means the binary search went wrong and the linear
        # fallback hid it.
        self.assertEqual(result.stderr, "")

    def test_reports_first_release_containing_commit(self):
        for n in range(1, 12):
            with self.subTest(release=n):
                self.assert_found(
                    self.run_script("nixos-26.05", self.commits[n - 1]), n)

    def test_follows_paged_listings(self):
        self.bucket.page = 4
        self.assert_found(self.run_script("nixos-26.05", self.commits[2]),
                          3)
        markers = [q.get("marker", "") for q in self.bucket.requests
                   if not q.get("prefix", "").endswith("/git-revision")]
        names = sorted(n for n, _ in
                       self.bucket.releases["nixos/26.05/"])
        self.assertEqual(markers, [
            "", "nixos/26.05/%s/" % names[3],
            "nixos/26.05/%s/" % names[7]])

    def test_short_commit_is_accepted(self):
        self.assert_found(
            self.run_script("nixos-26.05", self.commits[0][:7]), 1)

    def test_commit_no_release_contains_yet(self):
        self.git("commit", "-q", "--allow-empty", "-m", "later")
        later = self.git("rev-parse", "HEAD").strip()
        result = self.run_script("nixos-26.05", later)
        self.assertEqual(result.returncode, 1)
        self.assertIn("No nixos-26.05 release contains", result.stderr)

    def test_real_bucket_is_accepted(self):
        # Offline, the dead proxy makes the listing fail -- after the
        # argument checks have let the real bucket through.
        for bucket in (False, "https://nix-releases.s3.amazonaws.com"):
            with self.subTest(bucket=bucket):
                result = self.run_script("nixos-26.05", self.commits[0],
                                         bucket=bucket)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Invalid bucket", result.stderr)
                self.assertIn("Cannot list", result.stderr)

    def test_sed_e_flag_payload_does_not_run(self):
        # Closes the prefix's s command, then runs `touch pwned` via
        # GNU sed's e flag, then reopens an s command for the rest.
        channel = "nixos-x,X,;s,^,touch${IFS}pwned,e;s,Q"
        result = self.run_script(channel, self.commits[0])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pwned")),
                         "the sed payload ran")
        self.assert_refused(result, "Invalid channel")

    def test_unsafe_channels_are_refused(self):
        for channel in ("nixos-26.05,p", "nixos-26.05;q", "nixos-26 05",
                        "nixos-26.05&prefix=nixpkgs/", "nixos-26.05/x",
                        "nixos-26.05\n", "nixos-$(id)", "nixos-26.05*"):
            with self.subTest(channel=channel):
                self.bucket.requests.clear()
                self.assert_refused(self.run_script(channel,
                                                    self.commits[0]),
                                    "Invalid channel")

    def test_non_loopback_bucket_is_refused(self):
        # -b must not become a way to reach an unlisted host.
        for url in ("https://example.invalid", "http://127.0.0.1.example",
                    "http://127.0.0.1:80/x?d=1", "http://127.0.0.1:",
                    "http://localhost:80", "file:///etc/passwd",
                    self.bucket.url + "/"):
            with self.subTest(url=url):
                self.bucket.requests.clear()
                self.assert_refused(
                    self.run_script("nixos-26.05", self.commits[0],
                                    bucket=url),
                    "Invalid bucket")

    def test_repo_config_cannot_run_commands(self):
        # A repository the agent could plant and name with -r, set up
        # as a partial clone: looking up a missing object would start
        # a lazy fetch that runs the configured upload-pack command.
        evil = os.path.join(self.tmp, "evil")
        marker = os.path.join(self.tmp, "pwned-git")
        subprocess.run(["git", "init", "-q", evil], check=True,
                       env=GIT_ENV)
        for key, value in (
                ("core.repositoryformatversion", "1"),
                ("extensions.partialClone", "origin"),
                ("remote.origin.url", evil),
                ("remote.origin.promisor", "true"),
                ("remote.origin.uploadpack", "touch %s; false" % marker)):
            subprocess.run(["git", "-C", evil, "config", key, value],
                           check=True, env=GIT_ENV)
        result = subprocess.run(
            [SCRIPT, "-b", self.bucket.url, "-r", evil, "nixos-26.05",
             "0123456789abcdef0123456789abcdef01234567"],
            capture_output=True, text=True,
            env=dict(GIT_ENV, HOME=self.tmp), cwd=self.tmp, timeout=15)
        self.assertFalse(os.path.exists(marker),
                         "the repository's upload-pack command ran")
        self.assert_refused(result, "is not in")

    def test_unknown_channel_family_is_refused(self):
        self.assert_refused(self.run_script("debian-sid", self.commits[0]),
                            "Unknown channel")

    def test_non_hex_commits_are_refused(self):
        for commit in ("-p", "--output=x", "HEAD", "master",
                       self.commits[0][:6], self.commits[0] + "0",
                       self.commits[0][:7].upper()):
            with self.subTest(commit=commit):
                self.assert_refused(self.run_script("nixos-26.05", commit),
                                    "Invalid commit")


if __name__ == "__main__":
    unittest.main()
