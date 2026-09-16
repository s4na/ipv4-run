"""Executed by the SDK-selected Python interpreter before gcloud.py."""
import errno
import os
from pathlib import Path
import runpy
import socket
import sys

expected = os.environ.pop('_IPV4_RUN_ENTRY', '')
if len(sys.argv) < 2 or not expected or Path(sys.argv[1]).resolve() != Path(expected).resolve():
    sys.exit('ipv4-run: unsupported SDK launcher; refusing to run without the IPv4 hook')

_getaddrinfo = socket.getaddrinfo
_socket = socket.socket


def ipv4_getaddrinfo(host, port, family=socket.AF_UNSPEC, type=0, proto=0, flags=0):
    if family not in (socket.AF_UNSPEC, socket.AF_INET):
        raise socket.gaierror(socket.EAI_FAMILY, 'IPv6 disabled by ipv4-run')
    return _getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


class IPv4Socket(_socket):
    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
        if family == socket.AF_INET6:
            raise OSError(errno.EAFNOSUPPORT, 'IPv6 disabled by ipv4-run')
        super().__init__(family, type, proto, fileno)
        # Also reject IPv6 sockets adopted via a file descriptor.
        if self.family == socket.AF_INET6:
            self.close()
            raise OSError(errno.EAFNOSUPPORT, 'IPv6 disabled by ipv4-run')


socket.getaddrinfo = ipv4_getaddrinfo
socket.socket = IPv4Socket
# Do not propagate the bootstrap to gcloud's child launchers. Children are
# explicitly outside the restriction's scope, rather than recursively patched.
os.environ.pop('CLOUDSDK_PYTHON_ARGS', None)
sys.argv = sys.argv[1:]
sys.path.insert(0, str(Path(sys.argv[0]).parent))
runpy.run_path(sys.argv[0], run_name='__main__')
