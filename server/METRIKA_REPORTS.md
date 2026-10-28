# Scheduled Metrika reports

## 28 October 2026: daily and weekly presentation and source details

Daily/weekly digests lead with form and qualified CRM goal achievements, then traffic,
conversion sources, entry pages and an observation. Emoji headings and bullets replace
inline lists. Small comparison bases use previous absolute counts instead of large
percentages. Form and CRM counts are never summed as unique leads.

The read-only reporter queries goal 674189833 separately and adds independent aggregate
slices by channel, UTM campaign/content, Direct campaign/banner/platform and search phrase.
Rows without conversions are omitted, with top 3 daily / top 5 weekly and explicit overflow.
Provider-suppressed data stay unavailable. No ClientID, contact, CRM deal or visitor-history
join is performed; no attempt to reconstruct suppressed individual details. Search phrases
are not replaced by UTM keywords or autotargeting. Dynamic text is escaped and obvious
contacts/URLs removed. Optional API errors preserve the basic digest with an explicit gap.
CRM goals may augment earlier visit periods; this is not a daily CRM creation register.

Monthly formatting/collection, existing timer, credentials, dispatch and sent-state remain
unchanged. Known entry paths include current canonical routes as well as historical routes.
No new alerting, notification channel, access scope or backend/database connection.

Owner explicitly requested no tests or report runs/messages for this update. Do not run
check/preview/run or service start as part of installation. Read-only inspection of real
conversion data and file/diff/hash review are separate from report execution. Future visual
rendering/delivery is unverified until the next scheduled report.

Upgrade an existing reporter with `bash ops/upgrade-metrika.sh` from committed, pushed code.
It copies unchanged installed dependencies, verifies updated file hashes, locks the existing
state, records pointers/hashes, and atomically switches current/previous. It does not change
systemd/env/state or invoke the reporter. On verification failure it restores both pointers.
Inspect current/previous before any later rollback; retain the durable sent-state.
