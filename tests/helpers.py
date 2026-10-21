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
import shlex
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
# The caller's GIT_* variables are dropped: GIT_NO_LAZY_FETCH or
# GIT_ALLOW_PROTOCOL there would make the planted-repo tests pass
# against an unhardened helper, and GIT_DIR would redirect every call.
GIT_ENV = dict(
    {k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
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


# Base URLs a helper must refuse: anything but the real default or a
# loopback test server with a plain path.
BAD_URLS = ("https://example.invalid", "http://127.0.0.1.example",
            "http://127.0.0.1:80@example.invalid", "http://127.0.0.1:",
            "http://127.0.0.1:8x", "http://localhost:80", "file:///etc",
            "http://127.0.0.1:80/a?b=1")

# A commit id no fixture repository has.
MISSING = "0123456789abcdef0123456789abcdef01234567"


def planted_repo(path, marker, refs=()):
    """Make a repository the agent could plant and name with -r.

    It is set up as a partial clone whose upload-pack command creates
    `marker`, and each ref in `refs` (e.g. refs/remotes/origin/trunk)
    points at MISSING, so reading through one would start a lazy fetch
    and run the command.  A plain git lookup is run once first to
    prove that it does, so a git that stops lazy-fetching cannot turn
    the tests that use it into silent passes.  Returns `path`.
    """
    subprocess.run(["git", "init", "-q", path], check=True, env=GIT_ENV)
    for key, value in (
            ("core.repositoryformatversion", "1"),
            ("extensions.partialClone", "origin"),
            ("remote.origin.url", path),
            ("remote.origin.promisor", "true"),
            ("remote.origin.uploadpack",
             "touch %s; false" % shlex.quote(marker))):
        subprocess.run(["git", "-C", path, "config", key, value],
                       check=True, env=GIT_ENV)
    for ref in refs:
        ref_path = os.path.join(path, ".git", ref)
        os.makedirs(os.path.dirname(ref_path), exist_ok=True)
        with open(ref_path, "w") as f:
            f.write(MISSING + "\n")
    subprocess.run(["git", "-C", path, "cat-file", "-e", MISSING],
                   capture_output=True, env=GIT_ENV)
    if not os.path.exists(marker):
        raise AssertionError("planted repository did not lazy-fetch")
    os.unlink(marker)
    return path


def replaced_repo(path, marker, source, refs, rev, blob_path):
    """Make a repository that turns a file read into a command run.

    It borrows `source`'s objects through objects/info/alternates,
    points each ref in `refs` at `rev`, and replaces the blob at
    `rev:blob_path` with the commit `rev` (refs/replace), so that
    `git show rev:blob_path` shows a commit with a patch -- and runs
    the textconv driver that info/attributes and the config attach to
    every path, which creates `marker`.  A plain `git show` is run
    once to prove it.  Returns `path`.
    """
    subprocess.run(["git", "init", "-q", "--bare", path], check=True,
                   env=GIT_ENV)
    with open(os.path.join(path, "objects", "info", "alternates"),
              "w") as f:
        f.write(os.path.join(source, ".git", "objects") + "\n")
    blob = subprocess.run(
        ["git", "-C", source, "rev-parse", "%s:%s" % (rev, blob_path)],
        check=True, capture_output=True, text=True,
        env=GIT_ENV).stdout.strip()
    commit = subprocess.run(
        ["git", "-C", source, "rev-parse", rev + "^{commit}"],
        check=True, capture_output=True, text=True,
        env=GIT_ENV).stdout.strip()
    for ref in list(refs) + ["refs/replace/" + blob]:
        ref_path = os.path.join(path, ref)
        os.makedirs(os.path.dirname(ref_path), exist_ok=True)
        with open(ref_path, "w") as f:
            f.write(commit + "\n")
    with open(os.path.join(path, "info", "attributes"), "w") as f:
        f.write("* diff=evil\n")
    subprocess.run(["git", "-C", path, "config", "diff.evil.textconv",
                    "touch %s; cat" % shlex.quote(marker)],
                   check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", path, "show", "%s:%s" % (rev, blob_path)],
                   capture_output=True, env=GIT_ENV)
    if not os.path.exists(marker):
        raise AssertionError("replaced blob did not run textconv")
    os.unlink(marker)
    return path


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
