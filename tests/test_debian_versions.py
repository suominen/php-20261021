"""Tests for scripts/debian-versions, the Debian php8.x lookup.

Debian's php8.x package version is not something to compare against
the upstream PHP release: the level comes from the newest `New
upstream version X.Y.Z` changelog line, and anything above that line
is a backport whose tracked ids the script reports.  The web sources
are replaced by a loopback HTTP server over a tree laid out like the
real servers (missing files answer 404, as the real ones do):

  security-tracker/tracker/source-package/<src>   suite versions
  pts/media/packages/p/<src>/changelog-<ver>      changelog (tracker.d.o)
  ftp/changelogs/main/p/<src>/<src>_<ver>_changelog  (ftp-master fallback)
  sources/data/main/p/php-defaults/<ver>/debian/rules
"""

import os

from helpers import (FixtureServer, FixtureWeb, TempDirTest, rows, run,
                     script)

SCRIPT = script("debian-versions")


def source_page(src, versions):
    """The security tracker's source-package page, as one long line."""
    cells = "".join(
        "<tr><td>%s</td><td>%s</td></tr>" % (suite, ver)
        for suite, ver in versions
    )
    return (
        "<!DOCTYPE html><html><head><title>Information on source "
        "package %s</title></head><body><h1>Information on source "
        "package %s</h1><h2>Available versions</h2><table>"
        "<tr><th>Release</th><th>Version</th></tr>%s</table>"
        "<h2>Open issues</h2><table><tr><th>Bug</th></tr>"
        '<tr><td><a href="/tracker/CVE-2026-91765">CVE-2026-91765</a>'
        "</td><td>sid</td></tr></table></body></html>\n"
        % (src, src, cells)
    )


def changelog(entries):
    """entries: list of (version, dist, body-lines)."""
    out = []
    for version, dist, body in entries:
        out.append("php8.x (%s) %s; urgency=high\n\n" % (version, dist))
        out.extend("  %s\n" % line for line in body)
        out.append("\n -- Maintainer <m@example.invalid>  "
                   "Mon, 10 Aug 2026 18:44:03 +0200\n\n")
    return "".join(out)


def rules(default):
    return ("#!/usr/bin/make -f\n\nPHP_DEFAULT_VERSION    := %s\n"
            "PHP_SUPPORTED_VERSIONS := %s\n" % (default, default))


class DebianVersionsTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.web = FixtureWeb(os.path.join(self.tmp, "web"))
        self.server = FixtureServer(self.web)
        self.addCleanup(self.server.close)
        self.defaults({"bookworm": "93", "trixie": "96", "forky": "99",
                       "sid": "99"},
                      {"93": "8.2", "96": "8.4", "99": "8.4"})

    def defaults(self, suites, versions):
        self.web.put(
            "security-tracker/tracker/source-package/php-defaults",
            source_page("php-defaults", list(suites.items())))
        for ver, default in versions.items():
            self.web.put(
                "sources/data/main/p/php-defaults/%s/debian/rules" % ver,
                rules(default))

    def source(self, src, versions):
        self.web.put("security-tracker/tracker/source-package/" + src,
                     source_page(src, versions))

    def pts_changelog(self, src, version, text):
        clean = version.replace("~", "").replace("+", "")
        self.web.put("pts/media/packages/p/%s/changelog-%s"
                     % (src, clean), text)

    def ftp_changelog(self, src, version, text):
        self.web.put("ftp/changelogs/main/p/%s/%s_%s_changelog"
                     % (src, src, version), text)

    def lookup(self, *args):
        return run([
            SCRIPT,
            "-i", self.ids,
            "-D", self.server.url("sources"),
            "-F", self.server.url("ftp"),
            "-S", self.server.url("security-tracker"),
            "-T", self.server.url("pts"),
        ] + list(args))

    def seed_real_layout(self):
        self.source("php8.2", [("bookworm", "8.2.32-1~deb12u1"),
                               ("bookworm (security)",
                                "8.2.33-1~deb12u1")])
        self.source("php8.4", [("trixie", "8.4.24-1~deb13u1"),
                               ("trixie (security)", "8.4.24-1~deb13u1"),
                               ("forky", "8.4.24-1"),
                               ("sid", "8.4.24-1")])
        self.pts_changelog("php8.2", "8.2.33-1~deb12u1", changelog([
            ("8.2.33-1~deb12u1", "bookworm-security",
             ["* Non-maintainer upload by the LTS Team.",
              "* New upstream version 8.2.33:",
              "  + Fix CVE-2026-7260: Stack overflow in phar."]),
        ]))
        self.pts_changelog("php8.4", "8.4.24-1~deb13u1", changelog([
            ("8.4.24-1~deb13u1", "trixie-security",
             ["* New upstream version 8.4.24 (Closes: #1143153)"]),
        ]))
        self.pts_changelog("php8.4", "8.4.24-1", changelog([
            ("8.4.24-1", "unstable",
             ["* New upstream version 8.4.24"]),
        ]))

    def test_real_layout(self):
        self.seed_real_layout()
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout), [
            ("sid", "php8.4", "8.4.24-1", "8.4.24", "default", "-"),
            ("forky", "php8.4", "8.4.24-1", "8.4.24", "default", "-"),
            ("trixie-security", "php8.4", "8.4.24-1~deb13u1", "8.4.24",
             "default", "-"),
            ("bookworm-security", "php8.2", "8.2.33-1~deb12u1",
             "8.2.33", "default", "-"),
        ])

    def test_non_default_branch_in_a_suite(self):
        self.seed_real_layout()
        self.source("php8.5", [("sid", "8.5.11-1")])
        self.pts_changelog("php8.5", "8.5.11-1", changelog([
            ("8.5.11-1", "unstable", ["* New upstream version 8.5.11"]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[:2], [
            ("sid", "php8.4", "8.4.24-1", "8.4.24", "default", "-"),
            ("sid", "php8.5", "8.5.11-1", "8.5.11", "-", "-"),
        ])

    def test_backports_above_the_upstream_line(self):
        self.seed_real_layout()
        self.source("php8.2", [("bookworm (security)",
                                "8.2.33-1~deb12u2")])
        self.pts_changelog("php8.2", "8.2.33-1~deb12u2", changelog([
            ("8.2.33-1~deb12u2", "bookworm-security",
             ["* Fix CVE-2026-91765 (GHSA-rgrp-mwpx-f6rm).",
              "* Fix CVE-2025-14181.",
              # Longer id sharing a tracked prefix: not a match.
              "* Unrelated CVE-2026-61030."]),
            ("8.2.33-1~deb12u1", "bookworm-security",
             ["* New upstream version 8.2.33:",
              "  + Fix CVE-2026-91766 as listed in 8.2.33 NEWS."]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[-1], (
            "bookworm-security", "php8.2", "8.2.33-1~deb12u2", "8.2.33",
            "default",
            "CVE-2025-14181,CVE-2026-91765,GHSA-rgrp-mwpx-f6rm"))

    def test_ids_file_option_selects_the_ids(self):
        self.seed_real_layout()
        self.source("php8.2", [("bookworm (security)",
                                "8.2.33-1~deb12u2")])
        self.pts_changelog("php8.2", "8.2.33-1~deb12u2", changelog([
            ("8.2.33-1~deb12u2", "bookworm-security",
             ["* Fix CVE-2026-91765 (GHSA-rgrp-mwpx-f6rm).",
              "* Fix CVE-2025-14181."]),
            ("8.2.33-1~deb12u1", "bookworm-security",
             ["* New upstream version 8.2.33"]),
        ]))
        only = self.write_ids("CVE-2025-14181\n", "only-ids")
        result = self.lookup("-i", only)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout)[-1][5], "CVE-2025-14181")

    def test_missing_ids_file_fails(self):
        self.seed_real_layout()
        result = self.lookup("-i", os.path.join(self.tmp, "nope"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Cannot read " + os.path.join(self.tmp, "nope"),
                      result.stderr)

    def test_comment_only_ids_file_fails(self):
        self.seed_real_layout()
        empty = self.write_ids("# nothing tracked\n\n", "empty-ids")
        result = self.lookup("-i", empty)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("No ids in " + empty, result.stderr)

    def test_ftp_master_changelog_fallback(self):
        self.seed_real_layout()
        os.unlink(os.path.join(
            self.web.path, "pts/media/packages/p/php8.4/changelog-8.4.24-1"))
        self.ftp_changelog("php8.4", "8.4.24-1", changelog([
            ("8.4.24-1", "unstable", ["* New upstream version 8.4.24"]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[0][3], "8.4.24")

    def test_unreadable_changelog_is_unknown(self):
        self.seed_real_layout()
        os.unlink(os.path.join(
            self.web.path, "pts/media/packages/p/php8.4/changelog-8.4.24-1"))
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        out = rows(result.stdout)
        self.assertEqual(out[0], ("sid", "php8.4", "8.4.24-1", "?",
                                  "default", "?"))
        self.assertIn("changelog", result.stderr)

    def test_no_upstream_line_is_unknown_level(self):
        self.seed_real_layout()
        self.pts_changelog("php8.4", "8.4.24-1", changelog([
            ("8.4.24-1", "unstable", ["* Fix CVE-2026-91768."]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[0][3:], ("?", "default", "CVE-2026-91768"))

    def test_source_absent_from_debian_is_skipped(self):
        # php8.3 and php8.5 have no page (404), as today; the rows for
        # the sources that do exist are all still there.
        self.seed_real_layout()
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r[:2] for r in rows(result.stdout)], [
            ("sid", "php8.4"), ("forky", "php8.4"),
            ("trixie-security", "php8.4"),
            ("bookworm-security", "php8.2")])

    def test_server_error_on_source_page_fails(self):
        # A failure must never read as "not in Debian".
        self.seed_real_layout()
        self.server.fail.add("/security-tracker/tracker/source-package/"
                             "php8.3")
        result = self.lookup()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot fetch", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_server_error_on_changelog_fails(self):
        self.seed_real_layout()
        self.server.fail.add("/pts/media/packages/p/php8.4/"
                             "changelog-8.4.24-1")
        result = self.lookup()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot fetch", result.stderr)

    def test_unreachable_server_fails(self):
        self.seed_real_layout()
        result = run([SCRIPT, "-i", self.ids, "-S", "http://127.0.0.1:9"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot fetch", result.stderr)

    def test_missing_php_defaults_page_fails(self):
        self.seed_real_layout()
        os.unlink(os.path.join(
            self.web.path,
            "security-tracker/tracker/source-package/php-defaults"))
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php-defaults", result.stderr)

    def test_suite_without_php_defaults_fails(self):
        self.seed_real_layout()
        self.defaults({"bookworm": "93", "trixie": "96", "forky": "99"},
                      {"93": "8.2", "96": "8.4", "99": "8.4"})
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sid", result.stderr)

    def test_rules_without_default_version_fails(self):
        self.seed_real_layout()
        self.web.put("sources/data/main/p/php-defaults/99/debian/rules",
                     "#!/usr/bin/make -f\n")
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PHP_DEFAULT_VERSION", result.stderr)

    def test_several_non_default_sources_descend(self):
        self.seed_real_layout()
        self.source("php8.5", [("sid", "8.5.11-1")])
        self.source("php8.2", [("sid", "8.2.34-1"),
                               ("bookworm (security)",
                                "8.2.33-1~deb12u1")])
        for src, ver in (("php8.5", "8.5.11-1"), ("php8.2", "8.2.34-1")):
            self.pts_changelog(src, ver, changelog([
                (ver, "unstable",
                 ["* New upstream version %s" % ver.split("-")[0]]),
            ]))
        out = rows(self.lookup().stdout)
        self.assertEqual([r[:2] for r in out[:3]], [
            ("sid", "php8.4"), ("sid", "php8.5"), ("sid", "php8.2")])

    def test_ids_below_the_upstream_line_are_not_backports(self):
        # Within the upstream entry, what follows the upstream line is
        # that release's own fix list; only earlier lines count.
        self.seed_real_layout()
        self.pts_changelog("php8.2", "8.2.33-1~deb12u1", changelog([
            ("8.2.33-1~deb12u1", "bookworm-security",
             ["* Backport fix for CVE-2026-91768.",
              "* New upstream version 8.2.33:",
              "  + Fix CVE-2026-91766 as listed in NEWS."]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[-1][5], "CVE-2026-91768")

    def test_extra_argument_is_a_usage_error(self):
        result = run([SCRIPT, "extra"])
        self.assertEqual(result.returncode, 2)

    def test_plain_suite_used_without_security_row(self):
        self.seed_real_layout()
        self.source("php8.2", [("bookworm", "8.2.32-1~deb12u1")])
        self.pts_changelog("php8.2", "8.2.32-1~deb12u1", changelog([
            ("8.2.32-1~deb12u1", "bookworm-security",
             ["* New upstream version 8.2.32"]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[-1][:4], ("bookworm", "php8.2",
                                       "8.2.32-1~deb12u1", "8.2.32"))

    def test_unparseable_source_page_fails(self):
        # A layout change must not read as "no rows".
        self.seed_real_layout()
        self.web.put("security-tracker/tracker/source-package/php8.4",
                     "<html><body><p>Redesigned</p></body></html>\n")
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php8.4", result.stderr)

    def test_newer_plain_suite_row_wins(self):
        # A point release can put a newer build in the main archive
        # than the security archive still carries.
        self.seed_real_layout()
        self.source("php8.2", [("bookworm", "8.2.34-1~deb12u1"),
                               ("bookworm (security)",
                                "8.2.33-1~deb12u1")])
        self.pts_changelog("php8.2", "8.2.34-1~deb12u1", changelog([
            ("8.2.34-1~deb12u1", "bookworm",
             ["* New upstream version 8.2.34"]),
        ]))
        out = rows(self.lookup().stdout)
        self.assertEqual(out[-1][:4], ("bookworm", "php8.2",
                                       "8.2.34-1~deb12u1", "8.2.34"))

    def test_level_must_match_the_package_version(self):
        # An entry worded differently must not let an older "New
        # upstream version" line further down set the level.
        self.seed_real_layout()
        self.source("php8.4", [("sid", "8.4.26-1"), ("forky", "8.4.24-1"),
                               ("trixie", "8.4.24-1~deb13u1")])
        self.pts_changelog("php8.4", "8.4.26-1", changelog([
            ("8.4.26-1", "unstable", ["* Import upstream 8.4.26"]),
            ("8.4.24-1", "unstable", ["* New upstream version 8.4.24"]),
        ]))
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout)[0][2:4], ("8.4.26-1", "?"))
        self.assertIn("8.4.26-1", result.stderr)

    def test_default_source_missing_from_suite_fails(self):
        # sid's php-defaults moves to 8.5 before php8.5 reaches sid.
        self.seed_real_layout()
        self.defaults({"bookworm": "93", "trixie": "96", "forky": "99",
                       "sid": "100"},
                      {"93": "8.2", "96": "8.4", "99": "8.4",
                       "100": "8.5"})
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php8.5", result.stderr)
        self.assertIn("sid", result.stderr)

    def test_curl_is_bounded_by_timeouts(self):
        with open(SCRIPT) as f:
            text = f.read()
        self.assertIn("--max-time", text)
        self.assertIn("--connect-timeout", text)

    def test_missing_php_defaults_fails(self):
        self.seed_real_layout()
        os.unlink(os.path.join(
            self.web.path,
            "sources/data/main/p/php-defaults/96/debian/rules"))
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php-defaults", result.stderr)

    def test_help(self):
        result = run([SCRIPT, "-h"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
