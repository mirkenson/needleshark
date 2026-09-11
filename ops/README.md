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
