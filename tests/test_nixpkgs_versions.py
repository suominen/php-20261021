"""Tests for scripts/nixpkgs-versions, the php8x lookup per channel.

nixpkgs defines every PHP branch in one file,
pkgs/development/interpreters/php/default.nix, as `phpXY = mkPhp {
version = ...; }` blocks, and picks the default with `php = phpXY;`
in pkgs/top-level/all-packages.nix.  Channel pointers are read from a
loopback HTTP stand-in for channels.nixos.org.
"""

import os

from helpers import (BAD_URLS, MISSING, FixtureRepo, FixtureServer,
                     FixtureWeb, TempDirTest, planted_repo, replaced_repo,
                     rows, run, script)

SCRIPT = script("nixpkgs-versions")
PHP_DIR = "pkgs/development/interpreters/php"


def default_nix(versions, extra_by_attr=None, let=""):
    extra_by_attr = extra_by_attr or {}
    text = ("{ callPackage }:\nlet\n  mkPhp = args: args;\n%sin\n{\n"
            % let)
    for attr, version in versions.items():
        text += "  %s = mkPhp {\n" % attr
        text += '    version = "%s";\n' % version
        text += '    hash = "sha256-AAAA";\n'
        text += extra_by_attr.get(attr, "")
        text += "  };\n"
    return text + "}\n"


def all_packages(default="php84"):
    # The real file also has an unrelated `php = pkgs.php.override`
    # binding further down; it must not be read as the default.
    return (
        "{ pkgs }:\n{\n"
        "  # Set default PHP interpreter, extensions and packages\n"
        "  php = %s;\n"
        "  phpExtensions = recurseIntoAttrs php.extensions;\n"
        "  foo = callPackage ./foo {\n"
        "    php = pkgs.php.override { embedSupport = true; };\n"
        "  };\n"
        "}\n" % default
    )


def tree(versions, default="php84", extra_by_attr=None, generic="",
         let=""):
    return {
        PHP_DIR + "/default.nix": default_nix(versions, extra_by_attr, let),
        PHP_DIR + "/generic.nix": "{ version }:\n{\n%s}\n" % generic,
        "pkgs/top-level/all-packages.nix": all_packages(default),
    }


NEW = {"php82": "8.2.34", "php83": "8.3.35", "php84": "8.4.26",
       "php85": "8.5.11"}
OLD = {"php82": "8.2.33", "php83": "8.3.33", "php84": "8.4.25",
       "php85": "8.5.10"}


class NixpkgsVersionsTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.repo = FixtureRepo(os.path.join(self.tmp, "nixpkgs"))
        self.web = FixtureWeb(os.path.join(self.tmp, "channels"))
        self.server = FixtureServer(self.web)
        self.addCleanup(self.server.close)

    def channel(self, name, sha):
        self.web.put(name + "/git-revision", sha)

    def lookup(self, *args):
        return run([SCRIPT, "-i", self.ids, "-c", self.server.url(),
                    "-r", self.repo.path] + list(args))

    def test_channel_and_branch_rows(self):
        old = self.repo.commit(tree(OLD))
        new = self.repo.commit(tree(NEW))
        self.repo.publish("master", new)
        self.channel("nixos-unstable", old)
        result = self.lookup("branch:master", "nixos-unstable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows(result.stdout), [
            ("branch:master", "php84", "8.4.26", "default", "-"),
            ("branch:master", "php85", "8.5.11", "-", "-"),
            ("branch:master", "php83", "8.3.35", "-", "-"),
            ("branch:master", "php82", "8.2.34", "-", "-"),
            ("nixos-unstable", "php84", "8.4.25", "default", "-"),
            ("nixos-unstable", "php85", "8.5.10", "-", "-"),
            ("nixos-unstable", "php83", "8.3.33", "-", "-"),
            ("nixos-unstable", "php82", "8.2.33", "-", "-"),
        ])

    def test_default_attr_comes_first(self):
        self.repo.publish("master", self.repo.commit(
            tree(NEW, default="php85")))
        out = rows(self.lookup("branch:master").stdout)
        self.assertEqual([(r[1], r[3]) for r in out], [
            ("php85", "default"), ("php84", "-"), ("php83", "-"),
            ("php82", "-")])

    def test_patch_ids_scoped_to_their_block(self):
        # nixfmt layout, in a middle block, with a nested attrset whose
        # own `};` must not end the block early.
        extra = {"php83": (
            "    extraPatches = [\n"
            "      (fetchpatch {\n"
            '        name = "CVE-2026-91765.patch";\n'
            '        url = "https://example.invalid/a.patch";\n'
            "      })\n"
            "    ];\n"
            "    meta = {\n"
            '      knownVulnerabilities = [ ];\n'
            "    };\n"
            '    extraNote = "GHSA-ch8v-r6jh-4vvr";\n')}
        generic = "  # fixes CVE-2025-1218 for every branch\n"
        self.repo.publish("master", self.repo.commit(
            tree(OLD, extra_by_attr=extra, generic=generic)))
        out = {r[1]: r[4] for r in rows(self.lookup("branch:master")
                                        .stdout)}
        self.assertEqual(
            out["php83"],
            "CVE-2026-91765,GHSA-ch8v-r6jh-4vvr,generic:CVE-2025-1218")
        for attr in ("php82", "php84", "php85"):
            self.assertEqual(out[attr], "generic:CVE-2025-1218")

    def test_ids_outside_the_blocks_are_generic(self):
        let = '  basePatches = [ ./CVE-2026-91767.patch ];\n'
        self.repo.publish("master", self.repo.commit(
            tree(OLD, let=let)))
        out = {r[1]: r[4] for r in rows(self.lookup("branch:master")
                                        .stdout)}
        self.assertEqual(set(out.values()), {"generic:CVE-2026-91767"})

    def test_ids_file_option_selects_the_ids(self):
        let = ('  basePatches = [ ./CVE-2026-91767.patch'
               ' ./CVE-2025-1218.patch ];\n')
        self.repo.publish("master", self.repo.commit(
            tree(OLD, let=let)))
        only = self.write_ids("CVE-2025-1218\n", "only-ids")
        result = self.lookup("-i", only, "branch:master")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = {r[1]: r[4] for r in rows(result.stdout)}
        self.assertEqual(set(out.values()), {"generic:CVE-2025-1218"})

    def test_missing_ids_file_fails(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        result = self.lookup("-i", os.path.join(self.tmp, "nope"),
                             "branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Cannot read " + os.path.join(self.tmp, "nope"),
                      result.stderr)

    def test_comment_only_ids_file_fails(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        empty = self.write_ids("# nothing tracked\n\n", "empty-ids")
        result = self.lookup("-i", empty, "branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("No ids in " + empty, result.stderr)

    def test_non_loopback_channel_url_is_refused(self):
        for url in BAD_URLS:
            with self.subTest(url=url):
                result = run([SCRIPT, "-i", self.ids, "-c", url,
                              "-r", self.repo.path, "nixos-unstable"])
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("Invalid base URL", result.stderr)

    def test_unsafe_channel_names_are_refused(self):
        for channel in ("-x", "--output=x", "../x", "x..y", "x;y", "x$y",
                        "x?y", "x@y"):
            with self.subTest(channel=channel):
                # After --, so -x reaches the channel check, not getopts.
                result = self.lookup("--", channel)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("Invalid channel", result.stderr)

    def test_replaced_blob_does_not_run_textconv(self):
        # A repository built from plain files: the clone's objects via
        # alternates, and a replace ref that turns the file the helper
        # reads into a commit, whose diff runs a textconv driver.
        sha = self.repo.commit(tree(NEW))
        self.repo.publish("master", sha)
        marker = os.path.join(self.tmp, "pwned")
        evil = replaced_repo(os.path.join(self.tmp, "evil"), marker,
                             self.repo.path,
                             ["refs/remotes/origin/master"], sha,
                             PHP_DIR + "/default.nix")
        result = self.lookup("-r", evil, "branch:master")
        self.assertFalse(os.path.exists(marker),
                         "the repository's textconv driver ran")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_planted_repo_config_does_not_run(self):
        self.channel("nixos-unstable", MISSING)
        for n, channel in enumerate(("branch:master", "nixos-unstable")):
            with self.subTest(channel=channel):
                # A repository and marker per path, so one regression
                # does not fail the other subtest as well.
                marker = os.path.join(self.tmp, "pwned-%d" % n)
                evil = planted_repo(os.path.join(self.tmp, "evil-%d" % n),
                                    marker,
                                    refs=["refs/remotes/origin/master"])
                result = self.lookup("-r", evil, channel)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(os.path.exists(marker),
                                 "the repository's upload-pack ran")

    def test_longer_id_is_not_a_match(self):
        extra = {"php84": '    note = "CVE-2026-61030";\n'}
        self.repo.publish("master", self.repo.commit(
            tree(OLD, extra_by_attr=extra)))
        out = {r[1]: r[4] for r in rows(self.lookup("branch:master")
                                        .stdout)}
        self.assertEqual(out["php84"], "-")

    def test_missing_default_line_fails(self):
        files = tree(NEW)
        files["pkgs/top-level/all-packages.nix"] = "{ pkgs }:\n{\n}\n"
        self.repo.publish("master", self.repo.commit(files))
        result = self.lookup("branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("default php", result.stderr)

    def test_missing_generic_nix_is_tolerated(self):
        files = tree(NEW)
        del files[PHP_DIR + "/generic.nix"]
        self.repo.publish("master", self.repo.commit(files))
        result = self.lookup("branch:master")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(rows(result.stdout)), 4)

    def test_removed_attr_is_absent(self):
        versions = dict(NEW)
        del versions["php82"]
        self.repo.publish("master", self.repo.commit(tree(versions)))
        out = rows(self.lookup("branch:master").stdout)
        self.assertEqual(out[-1], ("branch:master", "php82", "-", "-",
                                   "absent"))

    def test_unparseable_block_fails(self):
        # Defined but no literal version: a parser miss, not "absent".
        text = default_nix(NEW).replace('version = "8.3.35";',
                                        "version = base.version;")
        files = tree(NEW)
        files[PHP_DIR + "/default.nix"] = text
        self.repo.publish("master", self.repo.commit(files))
        result = self.lookup("branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php83", result.stderr)

    def test_version_must_match_the_attribute(self):
        text = default_nix(NEW).replace('"8.3.35"', '"8.4.26"')
        files = tree(NEW)
        files[PHP_DIR + "/default.nix"] = text
        self.repo.publish("master", self.repo.commit(files))
        result = self.lookup("branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php83", result.stderr)

    def test_missing_default_attr_fails(self):
        versions = dict(NEW)
        del versions["php84"]
        self.repo.publish("master", self.repo.commit(tree(versions)))
        result = self.lookup("branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("php84", result.stderr)

    def test_default_ignores_nested_php_assignments(self):
        files = tree(NEW)
        files["pkgs/top-level/all-packages.nix"] = (
            "{ pkgs }:\n{\n"
            "  foo = callPackage ./foo { php = php83; };\n"
            "  bar = callPackage ./bar {\n"
            "    php = php82;\n"
            "  };\n"
            "  php = php84;\n"
            "}\n")
        self.repo.publish("master", self.repo.commit(files))
        out = rows(self.lookup("branch:master").stdout)
        self.assertEqual(out[0][1:4], ("php84", "8.4.26", "default"))

    def test_stale_clone_warns(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        result = self.lookup("branch:master")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not fetched", result.stderr)

    def test_fresh_clone_does_not_warn(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        open(os.path.join(self.repo.path, ".git", "FETCH_HEAD"),
             "w").close()
        result = self.lookup("branch:master")
        self.assertEqual(result.stderr, "")

    def test_missing_default_nix_fails(self):
        self.repo.publish("master", self.repo.commit(
            {"pkgs/top-level/all-packages.nix": all_packages()}))
        result = self.lookup("branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("default.nix", result.stderr)

    def test_unknown_revision_is_unresolved(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        self.channel("nixos-unstable", "0" * 40)
        result = self.lookup("nixos-unstable")
        self.assertEqual(result.returncode, 3)
        self.assertIn(" of nixos-unstable ", result.stderr)
        self.assertIn("fetch the clone", result.stderr)
        self.assertEqual(rows(result.stdout), [
            ("nixos-unstable", "php85", "-", "-", "unresolved"),
            ("nixos-unstable", "php84", "-", "-", "unresolved"),
            ("nixos-unstable", "php83", "-", "-", "unresolved"),
            ("nixos-unstable", "php82", "-", "-", "unresolved"),
        ])

    def test_unknown_revision_does_not_stop_later_channels(self):
        new = self.repo.commit(tree(NEW))
        self.repo.publish("master", new)
        self.channel("nixos-unstable", new)
        self.channel("nixos-unstable-small", "0" * 40)
        result = self.lookup("nixos-unstable", "nixos-unstable-small",
                             "branch:master")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(rows(result.stdout), [
            ("nixos-unstable", "php84", "8.4.26", "default", "-"),
            ("nixos-unstable", "php85", "8.5.11", "-", "-"),
            ("nixos-unstable", "php83", "8.3.35", "-", "-"),
            ("nixos-unstable", "php82", "8.2.34", "-", "-"),
            ("nixos-unstable-small", "php85", "-", "-", "unresolved"),
            ("nixos-unstable-small", "php84", "-", "-", "unresolved"),
            ("nixos-unstable-small", "php83", "-", "-", "unresolved"),
            ("nixos-unstable-small", "php82", "-", "-", "unresolved"),
            ("branch:master", "php84", "8.4.26", "default", "-"),
            ("branch:master", "php85", "8.5.11", "-", "-"),
            ("branch:master", "php83", "8.3.35", "-", "-"),
            ("branch:master", "php82", "8.2.34", "-", "-"),
        ])
        warnings = [l for l in result.stderr.splitlines()
                    if "fetch the clone" in l]
        self.assertEqual(len(warnings), 1, result.stderr)
        self.assertIn(" of nixos-unstable-small ", warnings[0])

    def test_resolved_channels_exit_zero(self):
        new = self.repo.commit(tree(NEW))
        self.repo.publish("master", new)
        self.channel("nixos-unstable", new)
        result = self.lookup("nixos-unstable", "branch:master")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("unresolved", result.stdout)

    def test_pointer_that_is_not_a_commit_id_fails(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        # HEAD resolves in the clone; an error page or an empty body
        # must not pass for an unresolved revision either.
        for body in ("HEAD", "<html>Not Found</html>", "", "0" * 39,
                     "A" * 40):
            with self.subTest(body=body):
                self.channel("nixos-unstable", body)
                result = self.lookup("nixos-unstable")
                self.assertEqual(result.returncode, 1)
                self.assertIn("not a commit id", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_unreadable_channel_pointer_fails(self):
        result = self.lookup("nixos-99.99")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nixos-99.99", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_fatal_channel_stops_the_run(self):
        new = self.repo.commit(tree(NEW))
        self.repo.publish("master", new)
        self.channel("nixos-unstable", new)
        result = self.lookup("nixos-unstable", "nixos-99.99",
                             "branch:master")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual({r[0] for r in rows(result.stdout)},
                         {"nixos-unstable"})

    def test_missing_branch_fails(self):
        self.repo.publish("master", self.repo.commit(tree(NEW)))
        result = self.lookup("branch:release-99.99")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release-99.99", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_help(self):
        result = run([SCRIPT, "-h"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
