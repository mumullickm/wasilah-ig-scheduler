"""Print what a Facebook post actually carries: type, link, and the image the
Page is really rendering. Manual tool, takes the post id in POST_ID.
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]


def _get(path, params):
    p = dict(params); p["access_token"] = TOKEN
    try:
        return json.loads(urllib.request.urlopen(
            f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=30).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


pid = os.environ["POST_ID"]
r = _get(pid, {"fields": "message,permalink_url,full_picture,is_published,"
                         "attachments{type,title,url,unshimmed_url,media,target}"})
print(json.dumps(r, indent=2, ensure_ascii=False)[:4000])
