"""Loopback-only static preview; --live-api explicitly enables real submissions."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PreviewHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/leads':
            return self.reply(404, b'{"ok":false}')
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts or self.headers.get('Origin') not in {f'http://{host}' for host in hosts}:
            return self.reply(403, b'{"ok":false}')
        if not self.server.live_api:
            return self.reply(503, json.dumps({'ok': False, 'error': 'Отправка заявок в этом предпросмотре не подключена.'}).encode())
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 3 * 1024 * 1024:
                return self.reply(413, b'{"ok":false}')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, b'{"ok":false}')
            self.connection.settimeout(15)
            body = self.rfile.read(length)
            if len(body) != length:
                return self.reply(400, b'{"ok":false}')
            # Fixed destination, no credentials and no configurable external proxy.
            request = Request('https://needle-shark.ru/api/leads', data=body, method='POST',
                              headers={'Content-Type': 'application/json', 'Origin': 'https://needle-shark.ru'})
            with urlopen(request, timeout=30) as response:
                return self.reply(response.status, response.read(65536))
        except HTTPError as error:
            return self.reply(error.code, error.read(65536))
        except (URLError, OSError, ValueError):
            return self.reply(503, json.dumps({'ok': False, 'error': 'Не удалось получить подтверждение. Повторите отправку.'}).encode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--live-api', action='store_true', help='Forward form submissions to the existing live API')
    args = parser.parse_args()
    directory = str(Path(__file__).resolve().parent.parent / 'dist')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(PreviewHandler, directory=directory))
    server.live_api = args.live_api
    print(f'Preview: http://127.0.0.1:{args.port}/catalog/ (live API: {args.live_api})', flush=True)
    server.serve_forever()
