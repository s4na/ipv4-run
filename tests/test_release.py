import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous = Path.cwd()
        self.addCleanup(os.chdir, self.previous)
        root = Path(self.temp.name)
        self.remote = root / 'remote.git'
        self.repo = root / 'work'
        self.repo.mkdir()
        os.chdir(self.repo)
        self.git('init', '--bare', str(self.remote))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('remote', 'add', 'origin', str(self.remote))
        Path('Formula').mkdir()
        # Tests must not depend on the currently published version.
        source = (ROOT / 'Formula/ipv4-run.rb').read_text()
        import re
        source = re.sub(r'/tags/v[0-9.]+\.tar\.gz', '/tags/v0.1.0.tar.gz', source)
        Path('Formula/ipv4-run.rb').write_text(source)
        Path('README.md').write_text('**0.1.0** ipv4-run@0.1.0 は0.1.0のソース')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        baseline = self.git('rev-parse', 'HEAD')
        Path('.release-state.json').write_text(json.dumps(
            {'baseline': baseline, 'version': '0.1.0', 'releases': {}}))
        self.git('add', '.')
        self.git('commit', '-m', 'enable releases')
        self.prs = [self.pr(6)]
        Path('Formula/ipv4-run.rb').write_text(source + '# second PR install layout\n')
        Path('feature').write_text('second PR')
        self.git('add', '.')
        self.git('commit', '-m', 'second merge')
        self.prs.append(self.pr(7))
        self.git('push', '-u', 'origin', 'main')
        self.published = []
        self.original_run = release.run
        self.fail_brew = False

    def git(self, *args):
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL).strip()

    def pr(self, number):
        return {'number': number, 'merged_at': '2026-09-16T00:00:00Z',
                'merge_commit_sha': self.git('rev-parse', 'HEAD')}

    def fake_run(self, *args):
        if args[:2] == ('gh', 'api'):
            if '/pulls?' in args[-1]:
                return json.dumps([list(reversed(self.prs))])
            return json.dumps([[{'tag_name': tag} for tag in self.published]])
        if args[:3] == ('gh', 'release', 'create'):
            self.published.append(args[3])
            return ''
        if args[:2] == ('bash', 'scripts/test-homebrew.sh'):
            if self.fail_brew:
                raise RuntimeError('brew failure')
            return ''
        if '-m' in args and 'unittest' in args:
            return ''
        return self.original_run(*args)

    def execute(self):
        with patch.dict(os.environ, GITHUB_REPOSITORY='s4na/ipv4-run'), \
             patch.object(release, 'run', side_effect=self.fake_run), \
             patch.object(release, 'archive_digest', return_value='a' * 64), \
             patch('sys.argv', ['release.py']):
            release.main()

    def test_two_merges_order_tags_formula_push_and_rerun(self):
        self.execute()
        state = json.loads(Path('.release-state.json').read_text())
        self.assertEqual(state['version'], '0.1.2')
        self.assertEqual(state['releases']['6']['version'], '0.1.1')
        for pr, version in zip(self.prs, ('0.1.1', '0.1.2')):
            self.assertEqual(self.git('rev-parse', f'v{version}^{{commit}}'), pr['merge_commit_sha'])
            pinned = Path(f'Formula/ipv4-run@{version}.rb').read_text()
            self.assertIn(f'/tags/v{version}.tar.gz', pinned)
            self.assertIn('keg_only :versioned_formula', pinned)
            self.assertNotIn('  head ', pinned)
            self.assertEqual('# second PR install layout' in pinned, version == '0.1.2')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('rev-parse', 'origin/main'))
        self.assertIn('**0.1.2**', Path('README.md').read_text())
        head = self.git('rev-parse', 'HEAD')
        self.execute()
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.published, ['v0.1.1', 'v0.1.2'])

    def test_failure_after_tag_recovers_without_extra_bump(self):
        self.fail_brew = True
        with self.assertRaisesRegex(RuntimeError, 'brew failure'):
            self.execute()
        self.assertEqual(self.published, [])
        self.assertEqual(self.git('rev-parse', 'origin/main'), self.prs[-1]['merge_commit_sha'])
        self.git('reset', '--hard', 'origin/main')
        self.git('clean', '-fd')
        self.fail_brew = False
        self.execute()
        self.assertEqual(self.published, ['v0.1.1', 'v0.1.2'])

    def test_missing_github_release_is_repaired(self):
        self.execute()
        self.published.pop()
        head = self.git('rev-parse', 'HEAD')
        self.execute()
        self.assertEqual(self.published, ['v0.1.1', 'v0.1.2'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_conflicting_tag_is_not_moved(self):
        self.git('tag', 'v0.1.1')
        with self.assertRaisesRegex(RuntimeError, 'different commit'):
            release.ensure_tag('0.1.1', self.prs[0]['merge_commit_sha'])

    def test_unmerged_and_already_processed_prs_are_ignored(self):
        state = json.loads(Path('.release-state.json').read_text())
        state['releases']['6'] = {}
        self.prs[1]['merged_at'] = None
        self.assertEqual(release.pending_prs(state, self.prs), [])

    def test_push_rebases_over_a_concurrent_main_commit(self):
        peer = self.repo.parent / 'peer'
        self.git('clone', '--branch', 'main', str(self.remote), str(peer))
        self.git('-C', str(peer), 'config', 'user.name', 'Other')
        self.git('-C', str(peer), 'config', 'user.email', 'other@example.invalid')
        (peer / 'concurrent').write_text('new PR')
        self.git('-C', str(peer), 'add', '.')
        self.git('-C', str(peer), 'commit', '-m', 'concurrent merge')
        self.git('-C', str(peer), 'push', 'origin', 'main')
        Path('release-update').write_text('release')
        self.git('add', '.')
        self.git('commit', '-m', 'release update')
        release.push_update()
        self.assertEqual(Path('concurrent').read_text(), 'new PR')
        self.assertEqual(Path('release-update').read_text(), 'release')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('rev-parse', 'origin/main'))

    def test_patch_carry(self):
        self.assertEqual(release.next_patch('0.1.9'), '0.1.10')
