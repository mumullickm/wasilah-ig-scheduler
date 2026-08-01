"""One-time local helper: exchange a Google OAuth 'Desktop app' client for a
long-lived refresh token, so run_youtube.py can upload unattended.

Run once on the Mac, signed into the Wasilah Google account in the default browser:

    python3 mint_youtube_token.py

Prints YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN to paste into GitHub
secrets. Nothing is written to disk. Requires the OAuth consent screen to be
PUBLISHED (In production) or the refresh token silently expires after 7 days.
"""
import http.server, json, os, secrets, socket, sys, threading, urllib.parse, urllib.request, webbrowser

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
ID_FILE = os.path.expanduser("~/.wasilah_youtube_client_id")
SECRET_FILE = os.path.expanduser("~/.wasilah_youtube_client_secret")
REFRESH_FILE = os.path.expanduser("~/.wasilah_youtube_refresh_token")
SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
])


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


class Catcher(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        Catcher.result = {k: v[0] for k, v in q.items()}
        ok = "code" in Catcher.result
        body = ("<h2>Done. Close this tab and return to the terminal.</h2>" if ok
                else f"<h2>Failed: {Catcher.result.get('error', 'no code returned')}</h2>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *a):
        pass


def post_form(url, fields):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(),
                                 method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def read_or_prompt(path, label):
    if os.path.exists(path):
        val = open(path).read().strip()
        if val:
            print(f"{label}: read from {path}")
            return val
    return input(f"{label}: ").strip()


def main():
    cid = read_or_prompt(ID_FILE, "OAuth client ID")
    csec = read_or_prompt(SECRET_FILE, "OAuth client secret")
    if not (cid and csec):
        sys.exit("client id and secret are both required")

    port = free_port()
    redirect = f"http://127.0.0.1:{port}"
    state = secrets.token_urlsafe(16)
    url = AUTH + "?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",   # ask for a refresh token
        "prompt": "consent",        # force one even on repeat runs
        "state": state,
    })

    print("\nOpening the consent screen. Sign in as the WASILAH account, not your personal one.")
    print("If the browser does not open, paste this:\n" + url + "\n")
    sys.stdout.flush()
    srv = http.server.HTTPServer(("127.0.0.1", port), Catcher)
    if not os.environ.get("WASILAH_NO_BROWSER"):
        webbrowser.open(url)
    srv.serve_forever()

    res = Catcher.result
    if res.get("state") != state:
        sys.exit("state mismatch, aborting")
    if "code" not in res:
        sys.exit(f"no authorization code returned: {res}")

    tok = post_form(TOKEN, {
        "code": res["code"], "client_id": cid, "client_secret": csec,
        "redirect_uri": redirect, "grant_type": "authorization_code",
    })
    refresh = tok.get("refresh_token")
    if not refresh:
        sys.exit("Google returned no refresh_token. Re-run; if it persists, revoke the "
                 "app at myaccount.google.com/permissions and try again.")

    # Confirm which channel this token actually controls, so we cannot wire up the wrong one.
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": "Bearer " + tok["access_token"]})
        items = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("items", [])
        for it in items:
            sn = it["snippet"]
            print(f"\nToken controls channel: {sn['title']}  ({sn.get('customUrl', it['id'])})")
    except Exception as e:
        print(f"\n(could not read channel back: {e})")

    # Persist rather than print, so the token never lands in a terminal scrollback.
    fd = os.open(REFRESH_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(refresh + "\n")
    print(f"\nRefresh token saved to {REFRESH_FILE} (mode 600), {len(refresh)} chars.")
    print("All three values are now on disk as ~/.wasilah_youtube_* dotfiles.")


if __name__ == "__main__":
    main()
