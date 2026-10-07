"""Loopback-only B2B review: no production API, preview-only legacy URL redirects."""
import argparse
import json
import sys
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from preview import PreviewHandler


class B2BPreviewHandler(PreviewHandler):
    def do_GET(self):
        parsed=urlsplit(self.path)
        path=parsed.path
        if path.endswith('/index.html'):
            path=path[:-10]
        target=self.server.redirects.get(path.rstrip('/')+'/')
        if target:
            destination=urlsplit(target)
            self.send_response(301)
            self.send_header('Location',urlunsplit(('', '', destination.path,parsed.query,destination.fragment)))
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length','0')
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('X-Robots-Tag','noindex, nofollow')
        super().end_headers()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'outputs/b2b-preview')
    parser.add_argument('--port',type=int,default=4190)
    args=parser.parse_args()
    directory=args.directory.resolve()
    if directory == ROOT/'dist':
        parser.error('Use generated B2B preview output, not production dist')
    redirects=json.loads((directory/'preview-redirects.json').read_text())
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(B2BPreviewHandler,directory=str(directory)))
    server.live_api=False
    server.redirects=redirects
    print(f'B2B preview: http://127.0.0.1:{args.port}/ (local only; submissions disabled)',flush=True)
    server.serve_forever()
