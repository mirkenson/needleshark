# Needle Shark VPS

- Host: 194.87.99.98, Ubuntu 24.04.
- Primary domain: needle-shark.ru; www.needle-shark.ru, needleshark.ru and www.needleshark.ru redirect to it.
- Nginx config: /etc/nginx/sites-available/needle-shark.
- Public root: /var/www/needle-shark/current (symlink to a release).
- Deployment account: needledeploy (no sudo).
- SSH key stays outside this repo: ~/.ssh/needle_shark_ed25519.
- Publish from the local workspace: `bash ops/deploy.sh`.
- Each publish uploads a fresh release, then atomically switches current; previous points to the last release.
- Firewall allows TCP 22, 80, 443. Existing root access preserved for administration.
- The site serves HTTPS with HTTP redirects. Indexing is explicitly authorized by the owner on 11 September 2026. Form submissions use needle-leads on localhost:8091 via /api/leads.
- DNS A records for @ and www point to 194.87.99.98. Let's Encrypt covers all four names; certbot.timer handles renewal. Primary URL: https://needle-shark.ru/.
- GitHub source backup: https://github.com/mirkenson/needleshark. Save and push agreed changes before deploying the VPS. Existing .openai/hosting.json belongs to the separate Sites preview; VPS deployment does not use it.

Do not commit private keys, credentials or user-submitted data.

Before a static release, run `python3 blog/render.py`, `python3 catalog/render.py`, then `python3 ops/prepare-public.py`. The last command finalizes external-anchor UTM parameters and canonical URLs and regenerates robots.txt/sitemap.xml from approved blog/catalog data. Do not add draft HTML to dist. Resource URLs and internal links are not UTM-tagged.

Indexing configuration backup for the 11 September launch: `/etc/nginx/sites-available/needle-shark.pre-indexing-20260911`. Before reverting, inspect current/previous and this backup; restore only the matching verified version, run `nginx -t` before reload.

## Primary domain migration, 11 September 2026

The owner changed the two A records for needle-shark.ru (@ and www) to 194.87.99.98. The certificate lineage remains named needleshark.ru and now covers all four names. Keep its renewal active: HTTPS redirects also need valid certificates.

Install ops/needle-shark-leads.nginx.conf as /etc/nginx/snippets/needle-shark-leads.conf before using ops/needle-shark.nginx.conf. The API location is shared by the main HTTPS server and redirect aliases so already-open forms can still submit. Page redirects preserve the path and query. Unknown HTTP hosts retain 404. Prepare and test Nginx configuration before reload; the prior configuration is /etc/nginx/sites-available/needle-shark.pre-domain-20260911.

Publication source uses site_utils.ORIGIN for canonical, sitemap, robots and blog metadata. The backend accepts only the four owned HTTPS origins; new consent records name needle-shark.ru. Existing customer records are unchanged. Update the existing Metrika counter's primary/additional domain settings alongside the migration; do not replace the counter or its goals.

## Typography, images and SEO (11 September 2026)

Shared values: `dist/theme.css`; all typography: `dist/typography.css`; shared catalogue/blog navigation: `dist/navigation.css` + `dist/menu.js`. Instructions for future edits: `docs/TYPOGRAPHY.md` and `docs/SEO.md`. Existing page classes and design remain intact.

After adding/replacing an image, first run `python3 ops/optimize-images.py` with a local Python environment containing Pillow. It reads homepage originals and product images from `catalog/products.json`, creates responsive WebP derivatives and records dimensions/hashes in `ops/image-manifest.json`. The static site and server do not need Pillow. Originals are retained. For unchanged images do not recompress before each release.

Prepare and check a static change:

```sh
python3 blog/render.py
python3 catalog/render.py
python3 ops/prepare-public.py
python3 ops/check-site.py
python3 -m unittest discover -s blog -p 'test_*.py'
python3 -m unittest discover -s catalog -p 'test_*.py'
python3 -m unittest discover -s ops -p 'test_*.py'
python3 server/preview.py --port 4173
```

`check-site.py` is local and read-only. It validates page metadata/JSON-LD, sitemap, links, anchors, assets, image hashes and CSS tokens. Browser checks on the five documented widths are still required. The preview now resolves extensionless legal URLs like production. It does not send real submissions unless explicitly started with `--live-api`.

The optimization changes have not been installed on the VPS. Save/push the checked commit before publishing with `ops/deploy.sh`; the local browser tests do not count as a production or Google/email delivery check.
