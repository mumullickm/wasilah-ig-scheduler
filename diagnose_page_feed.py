#!/usr/bin/env python3
"""
Read-only diagnostic for the Hirra Page.

Confirmed by the founder: a logged-in non-admin sees FOUR stories on the Page.
Admin sees 64. Logged out sees ~1. That gradient tracks relationship to the
Page and to the publishing app, not privacy, which pass 1-4 proved is EVERYONE
on every story.

Hypothesis under test: the stories are being published by a Facebook App that is
in Development mode, or lacks the live permissions to publish publicly visible
content. Content published by an app in dev mode is visible only to people with
a role on that app or Page. That fits every observation at once:
  - admin sees all 64
  - a non-admin sees only the few posts NOT created by the app
  - the underlying photo OBJECT is still public, so /photo/?fbid= permalinks
    render logged out, which is what the 07-24 audit checked and trusted

So: which app created each story, and what mode is it in.
Writes nothing.
"""
import json, os, urllib.parse, urllib.request
from collections import Counter

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]


def _get(path, params=None):
    p = dict(params or {})
    p["access_token"] = TOKEN
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def err(e):
    if hasattr(e, "read"):
        try:
            return json.loads(e.read().decode())["error"]["message"][:400]
        except Exception:
            return str(e)
    return str(e)


def main():
    # 1. Which app owns this token, and is it live?
    print("=" * 70)
    print("TOKEN OWNER APP")
    print("=" * 70)
    try:
        d = _get("debug_token", {"input_token": TOKEN})
        print(json.dumps(d, indent=2)[:2500])
    except Exception as e:
        print(f"  debug_token ERROR {err(e)}")

    for path, fields in [
        ("app", "id,name,link,category,restrictions,app_type"),
        ("me/subscribed_apps", "")
    ]:
        try:
            print(f"\n--- /{path} ---")
            print(json.dumps(_get(path, {"fields": fields} if fields else None),
                             indent=2)[:1500])
        except Exception as e:
            print(f"  ERROR {err(e)}")

    # 2. Which application created each story, and is the story restricted?
    print("\n" + "=" * 70)
    print("PER-STORY APPLICATION + VISIBILITY")
    print("=" * 70)
    fields = ("id,created_time,status_type,permalink_url,"
              "application{id,name,link,namespace},"
              "privacy,is_hidden,is_published,"
              "targeting,feed_targeting")
    rows, page = [], 0
    data = _get("me/feed", {"fields": fields, "limit": 50})
    while True:
        rows.extend(data.get("data", []))
        page += 1
        nxt = (data.get("paging") or {}).get("next")
        if not nxt or page > 4:
            break
        with urllib.request.urlopen(nxt, timeout=60) as r:
            data = json.loads(r.read().decode())

    apps = Counter()
    promo = Counter()
    for r in rows:
        a = r.get("application") or {}
        apps[f"{a.get('id')} {a.get('name')}"] += 1
        promo[r.get("is_eligible_for_promotion")] += 1

    print(f"  stories inspected: {len(rows)}")
    print("\n  created by application:")
    for k, v in apps.most_common():
        print(f"    {v:4d}  {k}")
    print(f"\n  is_eligible_for_promotion: {dict(promo)}")

    print("\n  stories with NO application (created by a human in the UI):")
    for r in rows:
        if not r.get("application"):
            print(f"    {r.get('created_time')}  {r.get('status_type'):14s} "
                  f"{r.get('permalink_url')}")

    # 3. Sanity: how many stories are there in total, and what are the newest 6?
    print("\n  newest 6 stories and their app:")
    for r in rows[:6]:
        a = (r.get("application") or {}).get("name", "(none)")
        print(f"    {r.get('created_time')}  {a:28s} {r.get('permalink_url')}")


if __name__ == "__main__":
    main()
