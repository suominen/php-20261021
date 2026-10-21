"""Tests for scripts/scratch, the agent's only way to write a file.

scratch copies standard input to `.scratch-<name>` in the current
directory, which must be a git checkout's top (the worktree the agent
runs in), and refuses any name that could reach another file: one
holding a slash or anything outside a plain filename alphabet, or
not starting with a letter or digit (so no name reads as an option).  It
replaces an allowlisted tee, whose target could be any path the user
can write -- the worktree's own .claude/settings.json included.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "scripts", "scratch")


class ScratchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scratch-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(os.path.join(self.work, ".git"))
        os.makedirs(os.path.join(self.work, ".claude"))
        self.outside = os.path.join(self.tmp, "outside")
        with open(self.outside, "w") as f:
            f.write("untouched\n")

    def run_scratch(self, *args, data=b"payload\n", cwd=None):
        return subprocess.run(
            [SCRIPT] + list(args),
            input=data,
            capture_output=True,
            cwd=cwd or self.work,
            timeout=30,
        )

    def tree(self):
        """Every path under tmp, so a refusal can prove it wrote nothing."""
        found = set()
        for top, dirs, files in os.walk(self.tmp):
            for name in dirs + files:
                found.add(os.path.relpath(os.path.join(top, name),
                                          self.tmp))
        return found

    def read(self, name):
        with open(os.path.join(self.work, name), "rb") as f:
            return f.read()

    def assert_refused(self, *args, cwd=None):
        before = self.tree()
        res = self.run_scratch(*args, cwd=cwd)
        self.assertNotEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertNotEqual(res.stderr, b"")
        self.assertEqual(self.tree(), before, args)
        with open(self.outside) as f:
            self.assertEqual(f.read(), "untouched\n")

    def test_writes_stdin_to_prefixed_file(self):
        res = self.run_scratch("advisories.json", data=b'{"a": 1}\n')
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, b"")
        self.assertEqual(self.read(".scratch-advisories.json"),
                         b'{"a": 1}\n')

    def test_binary_and_empty_input(self):
        data = bytes(range(256)) * 16
        self.assertEqual(self.run_scratch("x.gz", data=data).returncode, 0)
        self.assertEqual(self.read(".scratch-x.gz"), data)
        self.assertEqual(self.run_scratch("empty", data=b"").returncode, 0)
        self.assertEqual(self.read(".scratch-empty"), b"")

    def test_overwrites_own_scratch_file(self):
        res = self.run_scratch("x", data=b"first, longer content\n")
        self.assertEqual(res.returncode, 0, res)
        res = self.run_scratch("x", data=b"second\n")
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(self.read(".scratch-x"), b"second\n")

    def test_hard_link_target_replaced_not_written_through(self):
        os.link(self.outside, os.path.join(self.work, ".scratch-x"))
        res = self.run_scratch("x", data=b"new\n")
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(self.read(".scratch-x"), b"new\n")
        with open(self.outside) as f:
            self.assertEqual(f.read(), "untouched\n")

    def test_git_file_marks_a_linked_worktree(self):
        os.rmdir(os.path.join(self.work, ".git"))
        with open(os.path.join(self.work, ".git"), "w") as f:
            f.write("gitdir: /elsewhere\n")
        res = self.run_scratch("x")
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(self.read(".scratch-x"), b"payload\n")

    def test_names_that_leave_the_prefix_refused(self):
        for name in ("", "a/b", "../outside", "/abs", "x y", "a\nb",
                     "-", "-rf", ".x", "_x", "*", "x\\y",
                     "settings.json/"):
            self.assert_refused(name)

    def test_inner_dots_dashes_underscores_allowed(self):
        res = self.run_scratch("a-b_c.d..e")
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(self.read(".scratch-a-b_c.d..e"), b"payload\n")

    def test_cannot_reach_claude_settings(self):
        self.assert_refused(".claude/settings.json")
        self.assert_refused("../work/.claude/settings.json")
        self.assertFalse(
            os.path.exists(os.path.join(self.work, ".claude",
                                        "settings.json")))

    def test_needs_exactly_one_name(self):
        self.assert_refused()
        self.assert_refused("a", "b")

    def test_refuses_outside_a_checkout_top(self):
        sub = os.path.join(self.work, ".claude")
        self.assert_refused("x", cwd=sub)
        self.assert_refused("x", cwd=self.tmp)

    def test_refuses_symlinked_target(self):
        os.symlink(self.outside, os.path.join(self.work, ".scratch-x"))
        self.assert_refused("x")

    def test_refuses_dangling_symlinked_target(self):
        # A link to a file that does not exist yet: a guard testing
        # -e or -f would miss it, and the write would create the
        # settings file the link names.
        target = os.path.join(self.work, ".claude", "settings.json")
        os.symlink(target, os.path.join(self.work, ".scratch-x"))
        self.assert_refused("x")
        self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
