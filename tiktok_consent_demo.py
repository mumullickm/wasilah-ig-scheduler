"""Local consent UI for the TikTok app-review demo recording.

    python3 tiktok_consent_demo.py          # serves http://127.0.0.1:8731/

WHY THIS EXISTS. TikTok's audit wants one continuous screen capture of a real
posting flow with a real consent surface: the creator's own name, a privacy
selector populated from creator_info/query, the interaction toggles, and the
commercial-content disclosure. run_tiktok.py has none of that, and correctly so
— it is a cron that posts Miraz's own videos with nobody in the loop. There is
therefore nothing to film. This page is the missing human-facing surface, and it
performs the SAME real API calls, so the recording is genuine rather than staged.
A mocked demo is the most common rejection reason.

WHAT IT POSTS. The app currently only holds the video.upload scope, because
video.publish is not offered until the Content Posting audit passes. So this
sends to the creator inbox as a draft (/post/publish/inbox/video/init/), which is
exactly what stage one is reviewed against. Once video.publish is granted, flip
DIRECT to True and it uses /post/publish/video/init/ with the chosen privacy
level instead.

The client secret never reaches the browser: the page talks to this local server,
and only this server talks to TikTok.

Reads the same home dotfiles as mint_tiktok_token.py:
    ~/.wasilah_tiktok_client_key
    ~/.wasilah_tiktok_client_secret
    ~/.wasilah_tiktok_refresh_token
"""
import http.server, json, os, socketserver, sys, urllib.parse, urllib.request

PORT = 8731
API = "https://open.tiktokapis.com/v2"
DIRECT = False          # flip to True once video.publish is granted
QUEUE = "tiktok.json"


def dotfile(name):
    """Raise, never sys.exit.

    This is called from inside request handlers. SystemExit there kills the
    connection with no response, so the browser shows a bare network failure and
    the cause is invisible — which, mid-recording, looks like the integration
    is broken. Raising surfaces the real reason as JSON in the page.
    """
    p = os.path.expanduser(f"~/.wasilah_tiktok_{name}")
    if not os.path.exists(p):
        raise RuntimeError(f"missing {p} — see mint_tiktok_token.py for how these are created")
    v = open(p).read().strip()
    if not v:
        raise RuntimeError(f"{p} is empty")
    return v


def access_token():
    body = urllib.parse.urlencode({
        "client_key": dotfile("client_key"),
        "client_secret": dotfile("client_secret"),
        "grant_type": "refresh_token",
        "refresh_token": dotfile("refresh_token"),
    }).encode()
    req = urllib.request.Request(
        f"{API}/oauth/token/", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if "access_token" not in d:
        raise RuntimeError(f"token refresh failed: {d}")
    return d["access_token"]


def tt_post(path, payload, token, timeout=120):
    req = urllib.request.Request(
        f"{API}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "Authorization": f"Bearer {token}"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


PAGE = """<!doctype html><meta charset=utf-8><title>Wasilah Publisher</title>
<style>
 body{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#123}
 h1{font-size:20px;margin:0 0 4px} .sub{color:#667;margin:0 0 24px}
 fieldset{border:1px solid #dde;border-radius:8px;margin:0 0 16px;padding:14px 16px}
 legend{font-weight:600;padding:0 6px} label{display:block;margin:7px 0}
 select,button{font:inherit;padding:8px 10px;border-radius:6px;border:1px solid #ccd}
 button{background:#0b6;color:#fff;border:0;padding:11px 18px;font-weight:600;cursor:pointer}
 button[disabled]{background:#bcc;cursor:not-allowed}
 .who{display:flex;align-items:center;gap:10px;margin-bottom:18px}
 .who img{width:44px;height:44px;border-radius:50%}
 .note{color:#667;font-size:13px;margin:8px 0 0} #out{white-space:pre-wrap;background:#f6f7f9;
 border-radius:8px;padding:12px;margin-top:16px;font:12px/1.5 ui-monospace,monospace}
 .warn{color:#b40;font-size:13px}
</style>
<h1>Wasilah Publisher</h1>
<p class=sub>Post a Wasilah video to TikTok</p>
<div class=who id=who>loading creator info…</div>

<fieldset><legend>Video</legend>
  <select id=video style=width:100%></select>
</fieldset>

<fieldset><legend>Who can view this video</legend>
  <select id=privacy style=width:100%><option value="">Select…</option></select>
  <p class=note>Options come from TikTok for this account.</p>
</fieldset>

<fieldset><legend>Interactions</legend>
  <label><input type=checkbox id=comment> Allow comments</label>
  <label><input type=checkbox id=duet> Allow Duet</label>
  <label><input type=checkbox id=stitch> Allow Stitch</label>
  <p class=note id=inote></p>
</fieldset>

<fieldset><legend>Disclose video content</legend>
  <label><input type=checkbox id=disclose> This video promotes a brand, product or service</label>
  <div id=dsub style=display:none;margin-left:22px>
    <label><input type=checkbox id=yourbrand> Your brand — promoting yourself or your own business</label>
    <label><input type=checkbox id=branded> Branded content — promoting another brand as a paid partnership</label>
    <p class=note id=dtext></p>
  </div>
</fieldset>

<button id=post disabled>Post to TikTok</button>
<p class=warn id=err></p>
<div id=out hidden></div>

<script>
const $ = i => document.getElementById(i)
let creator = null
const MUSIC = 'By posting, you agree to TikTok\\u2019s Music Usage Confirmation.'
const BRANDED = 'By posting, you agree to TikTok\\u2019s Branded Content Policy and Music Usage Confirmation.'

function refresh(){
  const d = $('disclose').checked
  $('dsub').style.display = d ? 'block' : 'none'
  $('dtext').textContent = $('branded').checked ? BRANDED : MUSIC
  // TikTok requires a privacy choice, and if disclosure is on, at least one kind.
  const ok = $('privacy').value && (!d || $('yourbrand').checked || $('branded').checked)
  $('post').disabled = !ok
  // Branded content cannot be private.
  const priv = $('privacy')
  if ($('branded').checked && priv.value === 'SELF_ONLY') { priv.value = ''; $('post').disabled = true }
}
;['privacy','disclose','yourbrand','branded'].forEach(i => $(i).addEventListener('change', refresh))

fetch('/api/creator').then(r => r.json()).then(d => {
  if (d.error) { $('who').textContent = 'Error: ' + d.error; return }
  creator = d
  $('who').innerHTML = (d.avatar ? '<img src="'+d.avatar+'">' : '') +
    '<div><b>' + d.nickname + '</b><br><span class=note>Posting to this TikTok account</span></div>'
  d.privacy_options.forEach(o => $('privacy').add(new Option(
    {PUBLIC_TO_EVERYONE:'Everyone', MUTUAL_FOLLOW_FRIENDS:'Friends', FOLLOWER_OF_CREATOR:'Followers', SELF_ONLY:'Only me'}[o]||o, o)))
  // Creator-level switches: if TikTok says they are off, the box is off and locked.
  ;[['comment','comment_disabled'],['duet','duet_disabled'],['stitch','stitch_disabled']].forEach(([id,k]) => {
    $(id).checked = !d[k]; $(id).disabled = d[k]
  })
  const off = [['Comments',d.comment_disabled],['Duet',d.duet_disabled],['Stitch',d.stitch_disabled]]
    .filter(x => x[1]).map(x => x[0])
  $('inote').textContent = off.length ? off.join(', ') + ' turned off in this account\\u2019s TikTok settings.' : ''
  d.videos.forEach(v => $('video').add(new Option(v.slug + ' — ' + v.caption, v.slug)))
  refresh()
})

$('post').addEventListener('click', () => {
  $('post').disabled = true; $('err').textContent = ''
  $('out').hidden = false; $('out').textContent = 'Uploading to TikTok…'
  fetch('/api/publish', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ slug: $('video').value, privacy: $('privacy').value,
      comment: $('comment').checked, duet: $('duet').checked, stitch: $('stitch').checked,
      disclose: $('disclose').checked, your_brand: $('yourbrand').checked,
      branded: $('branded').checked })})
   .then(r => r.json()).then(d => {
      $('out').textContent = JSON.stringify(d, null, 2)
      if (d.error) { $('err').textContent = d.error; $('post').disabled = false }
   })
})
</script>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/creator":
            try:
                token = access_token()
                d = tt_post("/post/publish/creator_info/query/", {}, token).get("data") or {}
                queue = json.load(open(QUEUE, encoding="utf-8"))
                return self._send(200, json.dumps({
                    "nickname": d.get("creator_nickname", "(unknown)"),
                    "avatar": d.get("creator_avatar_url", ""),
                    "privacy_options": d.get("privacy_level_options", []),
                    "comment_disabled": d.get("comment_disabled", False),
                    "duet_disabled": d.get("duet_disabled", False),
                    "stitch_disabled": d.get("stitch_disabled", False),
                    "videos": [{"slug": e["slug"],
                                "caption": e["caption"].split("\n")[0][:60]} for e in queue],
                }))
            except Exception as exc:
                return self._send(200, json.dumps({"error": str(exc)}))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/publish":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            queue = json.load(open(QUEUE, encoding="utf-8"))
            entry = next(e for e in queue if e["slug"] == req["slug"])
            video = urllib.request.urlopen(entry["video"], timeout=300).read()
            token = access_token()

            source = {"source": "FILE_UPLOAD", "video_size": len(video),
                      "chunk_size": len(video), "total_chunk_count": 1}
            if DIRECT:
                path = "/post/publish/video/init/"
                payload = {"post_info": {
                    "title": entry["caption"][:2200],
                    "privacy_level": req["privacy"],
                    "disable_comment": not req["comment"],
                    "disable_duet": not req["duet"],
                    "disable_stitch": not req["stitch"],
                    "brand_content_toggle": bool(req.get("branded")),
                    "brand_organic_toggle": bool(req.get("your_brand")),
                }, "source_info": source}
            else:
                # video.upload only reaches the creator's inbox as a draft.
                path = "/post/publish/inbox/video/init/"
                payload = {"source_info": source}

            init = tt_post(path, payload, token)
            data = init.get("data") or {}
            pid, url = data.get("publish_id"), data.get("upload_url")
            if not (pid and url):
                return self._send(200, json.dumps({"error": f"init failed: {init}"}))

            put = urllib.request.Request(url, data=video, method="PUT", headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(video)),
                "Content-Range": f"bytes 0-{len(video)-1}/{len(video)}"})
            urllib.request.urlopen(put, timeout=600)

            status = tt_post("/post/publish/status/fetch/", {"publish_id": pid}, token)
            return self._send(200, json.dumps({
                "mode": "DIRECT_POST" if DIRECT else "UPLOAD_TO_INBOX",
                "publish_id": pid, "bytes": len(video),
                "status": (status.get("data") or {}).get("status"),
                "next": ("Published to the profile." if DIRECT else
                         "Sent to the TikTok app inbox as a draft. Open TikTok to review and post."),
            }, indent=1))
        except Exception as exc:
            self._send(200, json.dumps({"error": str(exc)}))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if not os.path.exists(QUEUE):
        sys.exit(f"run this from the repo root; {QUEUE} not found")
    print(f"Wasilah Publisher consent UI: http://127.0.0.1:{PORT}/")
    print("mode:", "DIRECT_POST" if DIRECT else "UPLOAD_TO_INBOX (video.upload only)")
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
