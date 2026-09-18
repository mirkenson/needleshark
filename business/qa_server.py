"""Isolated browser QA: fake analytics and API, no database or outbound lead delivery."""
import json
import re
import socket
import sys
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'server')]
from business.render import build
from server.preview import PreviewHandler
from leads import validate

SDK = b'''(() => {
  const panel = document.createElement('details'); panel.id = 'qa-panel';
  panel.innerHTML = '<summary>LOCAL QA: analytics and API are simulated</summary><pre id="qa-events"></pre>';
  document.body.append(panel);
  const events = [];
  window.ym = (id, method, goal, params, callback) => {
    if (method === 'reachGoal') {
      events.push({id, goal, params});
      document.querySelector('#qa-events').textContent = JSON.stringify(events);
      callback?.();
    }
  };
})();'''


class QAHandler(PreviewHandler):
    attempts = {}
    records = []

    def do_GET(self):
        path = urlsplit(self.path).path
        scenario = parse_qs(urlsplit(self.path).query).get('qa_case', [''])[0]
        if path == '/business/' and scenario in ('text200', 'without-scripts'):
            html = (Path(self.directory) / 'business/index.html').read_text()
            if scenario == 'text200':
                html = html.replace('</head>', '<style>html{font-size:200%}</style></head>')
            else:
                html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
            body = html.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ('/metrika.js', '/__qa/records'):
            body = SDK if path == '/metrika.js' else json.dumps(self.records, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript' if path == '/metrika.js' else 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/leads':
            return self.reply(404, b'{"ok":false}')
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Origin') != origin:
            return self.reply(403, b'{"ok":false}')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 3 * 1024 * 1024:
            return self.reply(413, b'{"ok":false}')
        try:
            data = json.loads(self.rfile.read(length))
            if not data.get('name', '').startswith('ТЕСТ') or not data.get('contact', '').endswith('@example.com'):
                raise ValueError('QA accepts only synthetic test data')
            validated = validate(data)
        except (ValueError, TypeError) as error:
            return self.reply(400, json.dumps({'ok': False, 'error': str(error)}).encode())
        scenario = parse_qs(urlsplit(self.headers.get('Referer', '')).query).get('qa_case', ['success'])[0]
        self.attempts[data['id']] = self.attempts.get(data['id'], 0) + 1
        # Only synthetic data is accepted; record counts/context, never attachment bytes.
        self.records.append({'id': data['id'], 'attempt': self.attempts[data['id']], 'scenario': scenario,
                             'source_path': validated.get('source_path'), 'inquiry_type': validated.get('inquiry_type'),
                             'question': validated['question'], 'attachment': bool(validated.get('attachment'))})
        if scenario == 'retry' and self.attempts[data['id']] == 1:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.close_connection = True
            return
        if scenario == 'slow':
            time.sleep(4)
        if scenario == 'error':
            return self.reply(503, json.dumps({'ok': False, 'error': 'Тестовая ошибка сети. ' * 30}).encode())
        if scenario == 'wrong-id':
            return self.reply(202, b'{"ok":true,"id":"wrong"}')
        return self.reply(202, json.dumps({'ok': True, 'id': data['id']}).encode())


if __name__ == '__main__':
    directory = build('/tmp/needle-shark-business-qa')
    server = ThreadingHTTPServer(('127.0.0.1', 4176), partial(QAHandler, directory=str(directory)))
    server.live_api = False
    print('Isolated QA: http://127.0.0.1:4176/business/', flush=True)
    server.serve_forever()
