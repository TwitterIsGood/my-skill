---
name: linuxdo-article-reader
description: Fast LINUX DO / linux.do Discourse topic reader. Use when the user provides a linux.do topic URL, asks to read/check/summarize a LINUX DO article, says the site needs proxy 7890, or mentions using their logged-in Edge browser to access linux.do. Optimized for fetching the topic JSON in under 10 seconds using Microsoft Edge cookies and Discourse JSON endpoints.
---

# LINUX DO Article Reader

## Quick Path

Run the bundled script first:

```bash
python3 /Users/biangwua/.codex/skills/linuxdo-article-reader/scripts/fetch_topic.py "https://linux.do/t/topic/2504036"
```

Use `--post N` for a specific reply/post number, `--page N` for a Discourse page, and `--json` when raw topic JSON is needed.

The script:

- Reads only `linux.do` cookies from the logged-in Microsoft Edge profile.
- Auto-uses `http://127.0.0.1:7890` if that proxy port is open.
- Fetches `https://linux.do/t/topic/{topic_id}.json` directly.
- Uses `curl` with a temporary Netscape cookiejar rather than Python `urllib`, because Cloudflare may block urllib even with the same valid cookies.
- For reply URLs like `/152`, uses `?page=ceil(152/20)` instead of `/152.json`, because the latter often triggers Cloudflare.
- Prints topic metadata plus extracted post text without exposing cookies.

## Output Guidance

- For summaries, analysis, explanations, comparisons, and recommendations after fetching a topic, read and apply `references/talk-normal-output.md` before writing the final answer. This injects talk-normal style into linux.do topic work: direct, natural, no filler, and no canned AI phrasing.
- Preserve source fidelity. When the user asks for raw post text, quotes, usernames, timestamps, URLs, or extracted fields, do not rewrite those source materials; apply talk-normal only to your surrounding explanation or analysis.
- For topic summaries, lead with the practical takeaway, then list the key posts or evidence. Include the linux.do topic URL and post numbers when they matter.

## Pitfalls From Prior Runs

- Plain `curl https://linux.do/t/topic/{id}` may return an HTML 404 even when the logged-in topic exists.
- `https://linux.do/t/{id}.json`, `/t/topic/{id}/{post}.json`, and `/posts/{post_id}.json` can trigger Cloudflare even with some cookies.
- The reliable endpoint is usually `/t/topic/{id}.json`; use `?page=N` for later posts.
- Copying Edge's `Cookies` SQLite file is not enough: cookie values are encrypted and must be decrypted with the macOS Keychain item `Microsoft Edge Safe Storage`.
- Python `urllib` can be blocked by Cloudflare even with valid cookies; prefer `curl -b <temporary-cookiejar>` with a normal browser user agent.
- AppleScript can list Edge tab URLs/titles, but `execute javascript` is disabled unless the user enabled "Allow JavaScript from Apple Events", so do not depend on it.
- Browser screenshots and manual Edge automation are slow; use them only after the JSON path fails.
- AutoGLM/link readers may fail if their local token service is down; do not make them the primary path for linux.do.

## Fallbacks

If the script returns 403/Cloudflare:

1. Ask the user to open or refresh the topic in Edge once, then rerun the script so `cf_clearance` is fresh.
2. Retry with `--proxy http://127.0.0.1:7890` if auto proxy did not detect it.
3. Fetch the first-page JSON again with the script and only then try browser automation.

If the script returns 404:

1. Check that the URL has a valid numeric topic id.
2. The topic may be deleted/private, or the Edge account may not have access.
3. If the user can view it in Edge, refresh Edge cookies and rerun.

If Python says `cryptography` is missing, install or use the workspace runtime that provides it, then rerun the script.
