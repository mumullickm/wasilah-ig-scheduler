# Wasilah cloud publisher

GitHub Actions crons that publish Wasilah content to Instagram and the Facebook
Page on schedule, independent of any local machine. Token is the
`META_PAGE_TOKEN` repo secret. Each publisher keeps its own state file so a
missed or late run self-heals instead of silently dropping a post.

**Pull before editing.** The workflows commit state files back to `main`, so a
stale clone makes the self-heal look like a huge backlog.

## Publishers

| What | Script | Workflow | State |
|---|---|---|---|
| Quran-60 reels | `run_reels.py` | `publish-reels.yml` | `posted_reels.json` |
| Statics (IG feed + FB photo) | `run_statics.py` | `publish-statics.yml` | `posted_statics.json` |
| Blog links (FB only) | `run_links.py` | `publish-links.yml` | `posted_links.json` |
| Legacy Quran-60 | `run.js` | `publish.yml` | `posted.json` |

`diagnose_page_feed.py` (`diagnose.yml`, manual) dumps what the Page timeline
actually contains, to tell "public by permalink" apart from "visible on the
Page". Commits nothing.

## Blog links publisher

Facebook-only link posts pointing at wasilah.site articles. Instagram captions
cannot carry a clickable link, so cross-posting these would be noise.

Two things make it different from the other publishers:

**It uses Facebook's own scheduler, not the cron clock.** `run_links.py` posts
with `published=false` and `scheduled_publish_time`, handing each post to
Facebook in advance. Facebook then publishes at the exact minute even if a
runner is late or skipped, and the queue is visible in Meta Business Suite's
Scheduled tab where it can be edited or cancelled by hand. The cron is only a
daily safety net (09:00 BD) that registers anything in `links.json` not yet
handed over, so adding an entry is enough to get it queued.

**Facebook renders the card, we do not upload one.** `POST /{page}/feed` with
`message` + `link` makes Facebook scrape the URL, so the article's own
`og:image` becomes the link card. Each wasilah.site article has its own card at
`/blog/og/<slug>.jpg`; if a card looks wrong, fix the article's og tags rather
than this repo.

Adding a post: append `{slug, iso, message, link}` to `links.json` and either
wait for the daily tick or run `gh workflow run publish-links.yml --ref main`.
An `iso` in the past (or under ~15 minutes out) publishes immediately instead
of scheduling, which is the way to force a test post.

### Slot map, so publishers do not collide

Times are Dhaka (UTC+6).

| Slot | Who |
|---|---|
| 07:40 | statics |
| 13:05 | statics (batch 2, from 5 Aug) |
| 19:00 | legacy reels |
| **21:00** | **blog links (Mon + Thu)** |
| 21:05 | showcase statics, daily |
| 21:10 | reels (batch 1, to 3 Aug) |
| 21:35 | showcase statics on batch-1 reel days |
| 22:00 | reels (batch 2, from 5 Aug) |
| 22:10 | statics (batch 1, to 4 Aug) |

21:00 is deliberate: the audience is home by about 19:30 and settled before
dinner. It does mean three Wasilah posts land within ten minutes on Mondays and
Thursdays. Watch engagement on those days; if it thins out, move the blog links
to 20:00 rather than touching the showcase slot.

## Why not Meta Business Suite

Business Suite's composer builds these posts correctly and then refuses to
commit them: the Schedule button fires **zero** network requests, with no
console error and no validation message. It failed identically for a real mouse
and for automation, so it is not anti-automation. Ruled out: Instagram
co-target, the link attachment, scheduled-post caps, account restriction, and
acting as personal profile rather than the Page. Use the Graph API path above.
