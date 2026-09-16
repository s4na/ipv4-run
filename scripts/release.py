"""Publish one patch per merged PR; a committed ledger makes reruns idempotent."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

STATE = Path('.release-state.json')


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def next_patch(version):
    major, minor, patch = map(int, version.split('.'))
    return f'{major}.{minor}.{patch + 1}'


def pending_prs(state, prs):
    # First-parent order handles merges occurring in the same second as well.
    commits = run('git', 'rev-list', '--first-parent', '--reverse',
                  f'{state["baseline"]}..HEAD').splitlines()
    order = {sha: index for index, sha in enumerate(commits)}
    return sorted((pr for pr in prs if pr.get('merged_at')
                   and str(pr['number']) not in state['releases']
                   and pr['merge_commit_sha'] in order),
                  key=lambda pr: order[pr['merge_commit_sha']])


def update_files(version, digest, state, pr):
    formula = Path('Formula/ipv4-run.rb')
    source = run('git', 'show', f'{pr["merge_commit_sha"]}:Formula/ipv4-run.rb') + '\n'
    old = re.search(r'/tags/v(\d+\.\d+\.\d+)\.tar\.gz', source)[1]
    source = source.replace(f'/tags/v{old}.tar.gz', f'/tags/v{version}.tar.gz')
    source, count = re.subn(r'  sha256 "[0-9a-f]{64}"', f'  sha256 "{digest}"', source)
    if count != 1:
        raise RuntimeError('Expected exactly one source checksum')
    pinned = Path(f'Formula/ipv4-run@{version}.rb')
    if pinned.exists():
        raise RuntimeError(f'Refusing to overwrite {pinned}')
    pinned_source = source.replace('class Ipv4Run < Formula',
                                   f'class Ipv4RunAT{version.replace(".", "")} < Formula')
    pinned_source = re.sub(r'^  head .*$', '  keg_only :versioned_formula', pinned_source,
                           flags=re.MULTILINE)
    formula.write_text(source)
    pinned.write_text(pinned_source)
    old = state['version']
    readme = Path('README.md')
    readme.write_text(readme.read_text().replace(f'@{old}', f'@{version}')
                      .replace(f'**{old}**', f'**{version}**')
                      .replace(f'は{old}のソース', f'は{version}のソース'))
    state['version'] = version
    state['releases'][str(pr['number'])] = {'version': version, 'sha': pr['merge_commit_sha']}
    STATE.write_text(json.dumps(state, indent=2) + '\n')


def ensure_tag(version, sha):
    tag = f'v{version}'
    existing = subprocess.run(['git', 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}'],
                              capture_output=True, text=True)
    if existing.returncode == 0:
        if existing.stdout.strip() != sha:
            raise RuntimeError(f'{tag} already points to a different commit')
    else:
        run('git', 'tag', '-a', tag, sha, '-m', f'Release {tag}')
    run('git', 'push', 'origin', f'refs/tags/{tag}')


def archive_digest(repo, version):
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'source.tar.gz'
        run('curl', '--fail', '--location', '--retry', '5', '--retry-all-errors',
            '--output', str(archive),
            f'https://github.com/{repo}/archive/refs/tags/v{version}.tar.gz')
        return hashlib.sha256(archive.read_bytes()).hexdigest()


def ensure_release(repo, version, number):
    tag = f'v{version}'
    releases = json.loads(run('gh', 'api', '--paginate', '--slurp', f'repos/{repo}/releases'))
    if any(release['tag_name'] == tag for page in releases for release in page):
        return
    run('gh', 'release', 'create', tag, '--repo', repo, '--verify-tag', '--title', tag,
        '--notes', f'Automatic patch release for merged PR #{number}.')


def push_update():
    # Ordinary PR merges can advance main while brew tests run. Never force-push.
    for attempt in range(3):
        result = subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/main'])
        if result.returncode == 0:
            return
        if attempt < 2:
            run('git', 'fetch', 'origin', 'main')
            run('git', 'rebase', 'origin/main')
    raise RuntimeError('Could not push release update after three attempts')


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    if repo != 's4na/ipv4-run':
        raise RuntimeError('Releases are only published from s4na/ipv4-run')
    state = json.loads(STATE.read_text())
    pages = json.loads(run('gh', 'api', '--paginate', '--slurp',
                          f'repos/{repo}/pulls?state=closed&base=main&per_page=100'))
    pending = pending_prs(state, [pr for page in pages for pr in page])
    if '--dry-run' in sys.argv:
        print(json.dumps([pr['number'] for pr in pending]))
        return
    # Repair release publication if a previous run stopped after the main push.
    for number, release in state['releases'].items():
        ensure_release(repo, release['version'], number)
    for pr in pending:
        version = next_patch(state['version'])
        ensure_tag(version, pr['merge_commit_sha'])
        digest = archive_digest(repo, version)
        update_files(version, digest, state, pr)
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q')
        run('bash', 'scripts/test-homebrew.sh')
        run('git', 'diff', '--check')
        run('git', 'add', 'Formula', 'README.md', str(STATE))
        run('git', 'commit', '-m', f'chore: release v{version} (PR #{pr["number"]})')
        push_update()
        ensure_release(repo, version, pr['number'])
        print(f'Released v{version} for PR #{pr["number"]}', flush=True)


if __name__ == '__main__':
    main()
