# mod-host interface.

import socket

class ModHost:
    """Proxy object for communicating with mod-host."""

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(('127.0.0.1', 5555))

    def add(self, id: int, url: str) -> None:
        """Add the plugin identified by url as instance number 'id'."""
        self.socket.send(f'add {url} {id}\n'.encode())
        self._read_response()

    def remove(self, id: int) -> None:
        """Remove the plugin identified by "id"."""
        self.socket.send(f'remove {id}\n'.encode())
        return self._read_response()

    def bypass(self, id: int, bypass: bool) -> None:
        """Bypass/unbypass a given event."""
        self.socket.send(f'bypass {id} {1 if bypass else 0}\n'.encode())
        return self._read_response()

    def send_block(self, block: str) -> None:
        for line in block.split('\n'):
            line = line.strip()
            if line:
                print(f'sending: {line!r}')
                self.socket.send(line.encode() + b'\n')
                self._read_response()

    def param_set(self, id: int, symbol: str, value: float) -> None:
        self.socket.send(f'param_set {id} {symbol} {value}\n'.encode())
        self._read_response()

    def param_get(self, id: int, symbol: str) -> float:
        self.socket.send(f'param_get {id} {symbol}\n')
        self._read_response()

    def _read_response(self) -> str:
        response = b''
        while not response.endswith(b'\x00'):
            response += self.socket.recv(1024)
        print(f'response: {response}')
        return response
