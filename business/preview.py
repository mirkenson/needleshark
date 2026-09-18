"""Local B2B review server. Real lead submission is intentionally disabled."""
import argparse
import sys
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server.preview import PreviewHandler
from business.render import build


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4175)
    parser.add_argument('--output', default='/tmp/needle-shark-business-preview')
    args = parser.parse_args()
    directory = build(args.output)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(PreviewHandler, directory=str(directory)))
    server.live_api = False
    print(f'B2B prototype: http://127.0.0.1:{args.port}/business/ (submissions disabled)', flush=True)
    server.serve_forever()
