"""Tests for scripts/pkgsrc-versions, the lang/php8x lookup.

pkgsrc keeps every PHP branch's version in lang/php/phpversion.mk
(PHPxx_VERSION), names the package ${PHP_PKG_PREFIX}-${PHP_VERSION}
(php84-8.4.26), and sets PKGREVISION per lang/phpXX/Makefile -- so
DISTNAME is never the thing to read.
"""

import os

from helpers import (FixtureRepo, TempDirTest, planted_repo, replaced_repo,
                     rows, run, script)

SCRIPT = script("pkgsrc-versions")


def phpversion_mk(versions, default="84", extra=""):
    lines = ["# $NetBSD$", ""]
    for branch, version in versions.items():
        lines.append("PHP%s_VERSION=\t%s" % (branch, version))
    lines.append(extra)
    lines.append("PHP_VERSION_DEFAULT?=\t\t%s" % default)
    return "\n".join(lines) + "\n"


def php_makefile(branch, pkgrevision=None):
    text = (
        "# $NetBSD$\n\n"
        "PKGNAME=\t\t${PHP_PKG_PREFIX}-${PHP_VERSION}\n"
        "CATEGORIES=\t\tlang\n"
    )
    if pkgrevision is not None:
        text += "PKGREVISION=\t\t%s\n" % pkgrevision
    text += "PHP_VERSIONS_ACCEPTED=\t%s\n" % branch
    return text


def tree(versions, default="84", pkgrevisions=None, patches=None,
         extra=""):
    pkgrevisions = pkgrevisions or {}
    files = {"lang/php/phpversion.mk":
             phpversion_mk(versions, default, extra)}
    for branch in versions:
        files["lang/php%s/Makefile" % branch] = php_makefile(
            branch, pkgrevisions.get(branch))
        files["lang/php%s/patches/patch-configure.ac" % branch] = (
            "$NetBSD$\n\nBuild fix.\n")
    for rel, text in (patches or {}).items():
        files[rel] = text
    return files


ALL = {"82": "8.2.34", "83": "8.3.35", "84": "8.4.26", "85": "8.5.11"}
OLD = {"82": "8.2.33", "83": "8.3.33", "84": "8.4.25", "85": "8.5.10"}


class PkgsrcVersionsTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.repo = FixtureRepo(os.path.join(self.tmp, "pkgsrc"))

    def lookup(self, *args):
        return run([SCRIPT, "-i", self.ids, "-r", self.repo.path]
                   + list(args))

    def test_identifier_version_and_default(self):
        self.repo.publish("trunk", self.repo.commit(tree(ALL)))
        self.repo.publish("pkgsrc-2026Q3", self.repo.commit(
            tree(OLD, pkgrevisions={b: "1" for b in OLD})))
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout), [
            ("origin/trunk", "lang/php84", "php84-8.4.26", "8.4.26",
             "default", "-"),
            ("origin/trunk", "lang/php85", "php85-8.5.11", "8.5.11",
             "-", "-"),
            ("origin/trunk", "lang/php83", "php83-8.3.35", "8.3.35",
             "-", "-"),
            ("origin/trunk", "lang/php82", "php82-8.2.34", "8.2.34",
             "-", "-"),
            ("origin/pkgsrc-2026Q3", "lang/php84", "php84-8.4.25nb1",
             "8.4.25", "default", "-"),
            ("origin/pkgsrc-2026Q3", "lang/php85", "php85-8.5.10nb1",
             "8.5.10", "-", "-"),
            ("origin/pkgsrc-2026Q3", "lang/php83", "php83-8.3.33nb1",
             "8.3.33", "-", "-"),
            ("origin/pkgsrc-2026Q3", "lang/php82", "php82-8.2.33nb1",
             "8.2.33", "-", "-"),
        ])

    def test_pkgrevision_zero_adds_no_suffix(self):
        sha = self.repo.commit(tree(ALL, pkgrevisions={"84": "0"}))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual(out[0][2], "php84-8.4.26")

    def test_default_follows_php_version_default(self):
        sha = self.repo.commit(tree(ALL, default="85"))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual([(r[1], r[4]) for r in out[:4]], [
            ("lang/php85", "default"), ("lang/php84", "-"),
            ("lang/php83", "-"), ("lang/php82", "-")])

    def test_last_assignment_wins(self):
        # A pullup can leave the old line above the new one.
        extra = "PHP84_VERSION=\t8.4.27\n"
        sha = self.repo.commit(tree(ALL, extra=extra))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual(out[0][2:4], ("php84-8.4.27", "8.4.27"))

    def test_backport_patch_ids_are_reported(self):
        patches = {
            "lang/php82/patches/patch-ext_soap_php__http.c":
                "$NetBSD$\n\nFix CVE-2025-14181 (GHSA-cj93-vc83-wgqv).\n"
                "Also CVE-2026-91765.\n",
            # A longer id that merely starts with a tracked one must
            # not count as a match.
            "lang/php83/patches/patch-ext_phar_tar.c":
                "$NetBSD$\n\nUnrelated CVE-2026-61030.\n",
        }
        sha = self.repo.commit(tree(OLD, patches=patches))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual(
            out[3][5],
            "CVE-2025-14181,CVE-2026-91765,GHSA-cj93-vc83-wgqv")
        self.assertEqual(out[2][5], "-")

    def test_ids_file_option_selects_the_ids(self):
        patches = {
            "lang/php82/patches/patch-ext_soap_php__http.c":
                "$NetBSD$\n\nFix CVE-2025-14181 (GHSA-cj93-vc83-wgqv).\n",
        }
        sha = self.repo.commit(tree(OLD, patches=patches))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        only = self.write_ids("GHSA-cj93-vc83-wgqv\n", "only-ids")
        result = self.lookup("-i", only)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout)[3][5], "GHSA-cj93-vc83-wgqv")

    def test_missing_ids_file_fails(self):
        self.repo.publish("trunk", self.repo.commit(tree(ALL)))
        self.repo.publish("pkgsrc-2026Q3", self.repo.commit(tree(OLD)))
        result = self.lookup("-i", os.path.join(self.tmp, "nope"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Cannot read " + os.path.join(self.tmp, "nope"),
                      result.stderr)

    def test_comment_only_ids_file_fails(self):
        self.repo.publish("trunk", self.repo.commit(tree(ALL)))
        self.repo.publish("pkgsrc-2026Q3", self.repo.commit(tree(OLD)))
        empty = self.write_ids("# nothing tracked\n\n", "empty-ids")
        result = self.lookup("-i", empty)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("No ids in " + empty, result.stderr)

    def test_replaced_blob_does_not_run_textconv(self):
        # See the nixpkgs test of the same name.
        sha = self.repo.commit(tree(ALL))
        marker = os.path.join(self.tmp, "pwned")
        evil = replaced_repo(
            os.path.join(self.tmp, "evil"), marker, self.repo.path,
            ["refs/remotes/origin/trunk",
             "refs/remotes/origin/pkgsrc-2026Q3"],
            sha, "lang/php/phpversion.mk")
        result = self.lookup("-r", evil)
        self.assertFalse(os.path.exists(marker),
                         "the repository's textconv driver ran")

    def test_planted_repo_config_does_not_run(self):
        marker = os.path.join(self.tmp, "pwned")
        evil = planted_repo(
            os.path.join(self.tmp, "evil"), marker,
            refs=["refs/remotes/origin/trunk",
                  "refs/remotes/origin/pkgsrc-2026Q3"])
        result = self.lookup("-r", evil)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(marker),
                         "the repository's upload-pack ran")

    def test_missing_quarterly_branch_is_absent(self):
        self.repo.publish("trunk", self.repo.commit(tree(ALL)))
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        out = rows(result.stdout)
        self.assertEqual(out[4:], [
            ("origin/pkgsrc-2026Q3", "lang/php%s" % b, "-", "-", "-",
             "absent") for b in ("85", "84", "83", "82")])

    def test_missing_default_package_fails(self):
        files = tree(ALL)
        del files["lang/php84/Makefile"]
        del files["lang/php84/patches/patch-configure.ac"]
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lang/php84", result.stderr)

    def test_stale_clone_warns(self):
        sha = self.repo.commit(tree(ALL))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        result = self.lookup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not fetched", result.stderr)

    def test_fresh_clone_does_not_warn(self):
        sha = self.repo.commit(tree(ALL))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        open(os.path.join(self.repo.path, ".git", "FETCH_HEAD"),
             "w").close()
        self.assertEqual(self.lookup().stderr, "")

    def test_missing_package_on_a_branch_is_absent(self):
        versions = dict(ALL)
        del versions["85"]
        sha = self.repo.commit(tree(versions))
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual(out[1], ("origin/trunk", "lang/php85", "-", "-",
                                  "-", "absent"))

    def test_missing_trunk_fails(self):
        self.repo.publish("pkgsrc-2026Q3", self.repo.commit(tree(ALL)))
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("origin/trunk", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_package_without_version_fails(self):
        files = tree(ALL)
        files["lang/php/phpversion.mk"] = phpversion_mk(
            {b: v for b, v in ALL.items() if b != "83"})
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PHP83_VERSION", result.stderr)

    def test_missing_phpversion_mk_fails(self):
        files = tree(ALL)
        del files["lang/php/phpversion.mk"]
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("phpversion.mk", result.stderr)

    def test_missing_php_version_default_fails(self):
        files = tree(ALL)
        files["lang/php/phpversion.mk"] = files[
            "lang/php/phpversion.mk"].replace("PHP_VERSION_DEFAULT", "X")
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PHP_VERSION_DEFAULT", result.stderr)

    def test_unknown_pkgname_shape_is_unknown(self):
        files = tree(ALL, pkgrevisions={"83": "2"})
        files["lang/php83/Makefile"] = files["lang/php83/Makefile"].replace(
            "${PHP_PKG_PREFIX}-${PHP_VERSION}", "php-${PHP_VERSION}")
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        # No nbN is appended to an unknown name.
        self.assertEqual(out[2][1:4], ("lang/php83", "?", "8.3.35"))

    def test_pkgrevision_last_assignment_wins(self):
        files = tree(ALL, pkgrevisions={"84": "1"})
        files["lang/php84/Makefile"] += "PKGREVISION=\t\t3\n"
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        out = rows(self.lookup().stdout)
        self.assertEqual(out[0][2], "php84-8.4.26nb3")

    def test_unreadable_patch_fails(self):
        # git grep reports an unreadable file only on stderr, with the
        # same exit status as "no match": it must still fail the run
        # rather than print a row with no ids.
        files = tree(ALL)
        files["lang/php84/patches/patch-a"] = "$NetBSD$\n\nunique body\n"
        sha = self.repo.commit(files)
        self.repo.publish("trunk", sha)
        self.repo.publish("pkgsrc-2026Q3", sha)
        self.repo.drop_blob("origin/trunk", "lang/php84/patches/patch-a")
        result = self.lookup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git grep failed", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_not_a_clone_fails(self):
        result = run([SCRIPT, "-i", self.ids, "-r",
                      os.path.join(self.tmp, "nope")])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Not a git clone", result.stderr)

    def test_help(self):
        result = run([SCRIPT, "-h"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_extra_argument_is_a_usage_error(self):
        result = run([SCRIPT, "-r", self.repo.path, "extra"])
        self.assertEqual(result.returncode, 2)
