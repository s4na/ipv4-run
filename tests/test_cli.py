import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'bin' / 'ipv4-run'


class CLITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ipv4 run ')
        self.addCleanup(self.temp.cleanup)
        self.sdk = Path(self.temp.name)
        (self.sdk / 'bin').mkdir()
        (self.sdk / 'lib').mkdir()
        launcher = self.sdk / 'bin' / 'gcloud'
        launcher.write_text('#!/bin/sh\nexec "$TEST_PYTHON" $CLOUDSDK_PYTHON_ARGS '
                            '"$TEST_SDK/lib/gcloud.py" "$@"\n')
        launcher.chmod(0o755)
        self.env = os.environ.copy()
        for key in ('CLOUDSDK_PYTHON_ARGS', 'CLOUDSDK_USE_GOCLOUD'):
            self.env.pop(key, None)
        self.env.update(PATH=str(self.sdk / 'bin') + os.pathsep + self.env['PATH'],
                        TEST_PYTHON=sys.executable, TEST_SDK=str(self.sdk))

    def run_cli(self, code, *args, input=None):
        (self.sdk / 'lib' / 'gcloud.py').write_text(code)
        return subprocess.run([sys.executable, str(CLI), 'gcloud', *args],
                              env=self.env, input=input, text=True,
                              capture_output=True, timeout=10)

    def test_arguments_input_output_and_exit(self):
        result = self.run_cli('import sys,json\nprint(json.dumps(sys.argv[1:]))\n'
                              'print(input())\nprint("error",file=sys.stderr)\n'
                              'sys.exit(7)\n', 'a b', '', '--flag', input='hello\n')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.splitlines(), ['["a b", "", "--flag"]', 'hello'])
        self.assertEqual(result.stderr, 'error\n')

    def test_ipv4_resolution_and_connection(self):
        result = self.run_cli('''import socket, threading
server = socket.socket()
server.bind(('127.0.0.1', 0))
server.listen()
def serve():
    client, _ = server.accept()
    with client: client.sendall(b'IPv4 OK')
thread = threading.Thread(target=serve)
thread.start()
assert all(row[0] == socket.AF_INET for row in socket.getaddrinfo('localhost', 80))
with socket.create_connection(('localhost', server.getsockname()[1]), timeout=2) as client:
    print(client.recv(128).decode())
thread.join()
server.close()
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'IPv4 OK\n')

    def test_ipv6_and_literals_rejected(self):
        result = self.run_cli('''import socket
for operation in (
    lambda: socket.socket(socket.AF_INET6),
    lambda: socket.getaddrinfo('localhost', 80, socket.AF_INET6),
    lambda: socket.getaddrinfo('::1', 80),
):
    try: operation()
    except OSError: print('blocked')
    else: raise AssertionError('IPv6 unexpectedly allowed')
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['blocked'] * 3)

    def test_unix_socket_preserved(self):
        result = self.run_cli('import socket\ns=socket.socket(socket.AF_UNIX)\ns.close()\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_adopted_socket_families(self):
        result = self.run_cli("""import socket, _socket
# _socket represents sockets created before the Python hook was installed.
raw = _socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
with socket.socket(fileno=raw.detach()) as adopted:
    assert adopted.family == socket.AF_UNIX
try:
    raw = _socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
except OSError:
    print('IPv6 unavailable on host')
else:
    try: socket.socket(fileno=raw.detach())
    except OSError: print('blocked')
    else: raise AssertionError('adopted IPv6 socket was allowed')
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(result.stdout.strip(), ('blocked', 'IPv6 unavailable on host'))

    def test_signal_status(self):
        result = self.run_cli('import os,signal\nos.kill(os.getpid(),signal.SIGTERM)\n')
        self.assertEqual(result.returncode, -signal.SIGTERM)

    def test_sigint_with_live_stdin(self):
        (self.sdk / 'lib' / 'gcloud.py').write_text('import sys\nprint("ready",flush=True)\ninput()\n')
        process = subprocess.Popen([sys.executable, str(CLI), 'gcloud'], env=self.env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline(), 'ready\n')
            process.send_signal(signal.SIGINT)
            _, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn('KeyboardInterrupt', stderr)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_child_bootstrap_not_propagated(self):
        result = self.run_cli('import os\nassert "CLOUDSDK_PYTHON_ARGS" not in os.environ\n'
                              'assert "_IPV4_RUN_ENTRY" not in os.environ\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reject_custom_python_args(self):
        self.env['CLOUDSDK_PYTHON_ARGS'] = '-I'
        result = self.run_cli('raise AssertionError("must not run")\n')
        self.assertEqual(result.returncode, 2)
        self.assertIn('CLOUDSDK_PYTHON_ARGS', result.stderr)

    def test_reject_go_launcher(self):
        self.env['CLOUDSDK_USE_GOCLOUD'] = '1'
        result = self.run_cli('raise AssertionError("must not run")\n')
        self.assertEqual(result.returncode, 2)
        self.assertIn('CLOUDSDK_USE_GOCLOUD', result.stderr)

    def test_unknown_command_not_executed(self):
        result = subprocess.run([sys.executable, str(CLI), 'sh', '-c', 'echo executed'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_missing_gcloud(self):
        self.env['PATH'] = str(self.sdk / 'empty')
        result = self.run_cli('raise AssertionError("must not run")\n')
        self.assertEqual(result.returncode, 2)
        self.assertIn('not found', result.stderr)

    def test_incompatible_layout(self):
        result = subprocess.run([sys.executable, str(CLI), 'gcloud'], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('installation', result.stderr)

    def test_double_dash_and_explicit_path(self):
        (self.sdk / 'lib' / 'gcloud.py').write_text('print("ok")\n')
        result = subprocess.run([sys.executable, str(CLI), '--', str(self.sdk / 'bin/gcloud')],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'ok\n')

    def test_help(self):
        result = subprocess.run([sys.executable, str(CLI), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('gcloud', result.stdout)


if __name__ == '__main__':
    unittest.main()
