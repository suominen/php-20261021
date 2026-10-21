"""Shared fixtures for the lookup-helper tests.

Each helper reads either a git clone through its origin/... refs or a
set of web pages.  The fixtures build a throwaway git repository whose
remote-tracking refs are created directly with update-ref, and a
directory tree that stands in for the web servers through file://
URLs, so every test drives the real script with no network access.
"""

import functools
import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, os.pardir, "scripts")

# A dead proxy for every scheme, so a test that forgets to point a
# helper at its fixtures fails fast instead of reaching a real server;
# the loopback fixture server is exempt.
GIT_ENV = dict(
    os.environ,
    http_proxy="http://127.0.0.1:9",
    https_proxy="http://127.0.0.1:9",
    HTTPS_PROXY="http://127.0.0.1:9",
    ALL_PROXY="http://127.0.0.1:9",
    no_proxy="127.0.0.1",
    NO_PROXY="127.0.0.1",
    GIT_AUTHOR_NAME="Test",
    GIT_AUTHOR_EMAIL="test@example.invalid",
    GIT_COMMITTER_NAME="Test",
    GIT_COMMITTER_EMAIL="test@example.invalid",
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_NOSYSTEM="1",
)


# The ids every helper test searches for, passed with -i so the tests
# never depend on the tracker's own scripts/tracked-ids.  CVE-2026-6103
# is here so that CVE-2026-61030 in the fixtures exercises the
# longer-id-sharing-a-prefix case.
FIXTURE_IDS = """\
# Fixture ids: '#' lines and blank lines are ignored.

CVE-2025-1218
CVE-2025-14181
CVE-2026-6103
CVE-2026-91765
CVE-2026-91766
CVE-2026-91767
CVE-2026-91768
GHSA-ch8v-r6jh-4vvr
GHSA-cj93-vc83-wgqv
GHSA-rgrp-mwpx-f6rm
"""


def script(name):
    return os.path.join(SCRIPTS, name)


def run(argv, **kwargs):
    """Run a helper; return the CompletedProcess (text mode)."""
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env=kwargs.pop("env", GIT_ENV),
        timeout=kwargs.pop("timeout", 60),
        **kwargs,
    )


def rows(stdout):
    """Split tab-separated output into a list of tuples."""
    return [tuple(line.split("\t")) for line in stdout.splitlines()]


class FixtureRepo:
    """A git repository whose commits are published as origin/<ref>."""

    def __init__(self, path):
        self.path = path
        os.makedirs(path)
        self.git("init", "-q", "-b", "scratch")

    def git(self, *args, date=None):
        env = dict(GIT_ENV)
        if date:
            env["GIT_AUTHOR_DATE"] = date + "T12:00:00Z"
            env["GIT_COMMITTER_DATE"] = date + "T12:00:00Z"
        return subprocess.run(
            ["git", "-C", self.path] + list(args),
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()

    def commit(self, files, remove=(), date="2026-09-24"):
        """Write files ({path: text}), commit, and return the SHA."""
        for rel, text in files.items():
            full = os.path.join(self.path, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(text)
        for rel in remove:
            os.unlink(os.path.join(self.path, rel))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "fixture",
                 date=date)
        return self.git("rev-parse", "HEAD")

    def publish(self, ref, sha):
        """Point refs/remotes/origin/<ref> at sha."""
        self.git("update-ref", "refs/remotes/origin/" + ref, sha)

    def drop_blob(self, rev, path):
        """Delete the loose object behind rev:path, so reading that
        file's contents fails while the tree still lists it."""
        sha = self.git("rev-parse", "%s:%s" % (rev, path))
        os.unlink(os.path.join(self.path, ".git", "objects", sha[:2],
                               sha[2:]))


class FixtureWeb:
    """A directory tree served through file:// URLs."""

    def __init__(self, path):
        self.path = path
        os.makedirs(path)

    def put(self, rel, text):
        full = os.path.join(self.path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)

    def url(self, rel=""):
        return "file://" + os.path.join(self.path, rel).rstrip("/")


class FixtureServer:
    """Serve a FixtureWeb tree over HTTP on a loopback port.

    Missing files answer 404, as the real servers do; paths listed in
    `fail` answer 500, to stand in for a server or network failure.
    """

    def __init__(self, web):
        self.fail = set()
        fail = self.fail

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0] in fail:
                    self.send_error(500)
                    return
                super().do_GET()

            def log_message(self, *args):
                pass

        handler = functools.partial(Handler, directory=web.path)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                     handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)
        self.thread.start()

    def url(self, rel=""):
        host, port = self.httpd.server_address
        return ("http://%s:%d/%s" % (host, port, rel)).rstrip("/")

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="php-tracker-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.ids = self.write_ids(FIXTURE_IDS)

    def write_ids(self, text, name="tracked-ids"):
        """Write an ids file into the test's directory; return its path."""
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(text)
        return path
