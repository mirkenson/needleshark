# Needle Shark

Static homepage prototype for Needle Shark technical sewing production.

Live VPS site: https://needleshark.ru/

## Project

- `dist/`: authored HTML, CSS, JavaScript and public images. These files are source assets and must stay tracked.
- `ops/`: VPS Nginx configuration, deployment script and operations notes.
- `.openai/hosting.json`: metadata for the earlier, separate Sites preview.

## Preview locally

Run `python3 -m http.server 4173 --directory dist` and open http://localhost:4173/.

## Publish to VPS

Run `bash ops/deploy.sh` from a computer with the authorized SSH key. It uploads a new release and atomically switches the live symlink, preserving a reference to the previous release. See `ops/README.md`.

The request form is a demonstration and does not submit data. Product and review placeholders still need real content. Search indexing is currently discouraged using Nginx noindex headers.

Private SSH keys, TLS keys and credentials are not part of this repository. GitHub stores source history; it does not back up the server's private keys or future application data.
