"""Exercise the launcher installed by the Homebrew formula."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HomebrewLauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="brew python's ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'path'
        self.path.mkdir()
        self.cli = self.root / 'probe.py'
        self.cli.write_text('import json, os, sys\n'
                            'print(json.dumps([os.getenv("SELECTED", "fallback"), sys.argv[1:], input()]))\n'
                            'sys.exit(7)\n')
        self.launcher = self.root / 'ipv4-run'
        template = (ROOT / 'libexec/ipv4-run-homebrew.sh').read_text()
        self.launcher.write_text(template.replace('@CLI@', shlex.quote(str(self.cli)))
                                 .replace('@FALLBACK_PYTHON@', shlex.quote(sys.executable)))
        self.launcher.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.path))
        self.env.pop('SELECTED', None)

    def python_shim(self, body):
        shim = self.path / 'python3'
        shim.write_text('#!/bin/sh\n' + body)
        shim.chmod(0o755)

    def check(self, selected):
        import json
        result = subprocess.run([str(self.launcher), 'a b', '', '--flag'],
                                env=self.env, input='hello\n', text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(json.loads(result.stdout), [selected, ['a b', '', '--flag'], 'hello'])
        self.assertEqual(result.stderr, '')

    def test_path_python_preferred(self):
        self.python_shim('export SELECTED=path\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        self.check('path')

    def test_missing_python_falls_back(self):
        self.check('fallback')

    def test_old_python_falls_back(self):
        self.python_shim('exit 1\n')  # Version probe rejects Python < 3.10.
        self.check('fallback')

    def test_unconfigured_shim_falls_back_without_consuming_stdin(self):
        self.python_shim('read ignored\necho "mise: no version configured" >&2\nexit 127\n')
        self.check('fallback')

    def test_command_failure_does_not_retry_with_fallback(self):
        self.python_shim('if [ "$1" = -c ]; then exit 0; fi\nexit 42\n')
        result = subprocess.run([str(self.launcher)], env=self.env, input='',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(result.stdout, '')
