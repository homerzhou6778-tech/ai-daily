# Public profile deployment

This derivative uses `python scripts/update_news.py --public-only` exclusively.
It fetches the ten public example RSS/Atom subscriptions plus Anthropic News and
Follow Builders, bypassing all email, paid, Jina, service-status and LLM adapters
regardless of ambient integration environment variables. Private OPML is rejected.

The original mobile/classic UI and parsing/filtering/story-merge implementation
remain. Future-dated records are excluded from the 24-hour view. A successful
HTTP response containing no dated feed records is reported as a feed failure.
Fewer than six healthy sources aborts before overwriting the snapshot.

The workflow deploys an explicit static-file allowlist using GitHub Pages
artifacts. It does not push generated data back into the repository. Only public
archive history is cached. Mail digests, raw archives, source code and runtime
configuration are absent from the deployed artifact. A browser freshness notice
appears after four hours without a new snapshot.

Every deployment is followed by a live health probe. It checks the homepage,
RSS and consistent JSON snapshots, requiring a generated time at least as new
as the current build. Source degradation is distinct from an unusable site.
See `OPERATIONS.md` for independent monitoring and bounded recovery.

No user API credentials are required. GitHub's built-in deployment identity is
ephemeral; no PAT or login token is added to this repository.

Upstream code: LearnPrompt/ai-news-radar at
f138685aea3f928c50ab00507a8848a5463e3654 (MIT).
