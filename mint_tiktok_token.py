"""One-time local helper: exchange a TikTok app for a long-lived refresh token,
so run_tiktok.py can post unattended. Mirrors mint_youtube_token.py.

Run once on the Mac, signed into the Wasilah TikTok account in the default browser:

    python3 mint_tiktok_token.py            # Desktop app: localhost redirect + PKCE
    python3 mint_tiktok_token.py --manual   # Web app: paste the redirected URL back

Prints TT_CLIENT_KEY / TT_CLIENT_SECRET / TT_REFRESH_TOKEN to paste into GitHub
secrets. Nothing is written to disk, and nothing is printed anywhere but this
terminal.

WHICH MODE. TikTok's redirect rules differ by app type and getting it wrong wastes
a registration:
  - Desktop app: redirect MUST be localhost or 127.0.0.1, MUST carry a port, http
    is allowed, and PKCE is REQUIRED. That is the default mode here.
  - Web app: redirect MUST be absolute https on a public domain. localhost is
    rejected outright. Use --manual and register
    https://wasilah.site/tiktok/callback/ as the redirect.

Reads the client key and secret from home dotfiles, matching the rest of this
setup (~/.wasilah_gemini_key, ~/.elevenlabs_key and friends):

    ~/.wasilah_tiktok_client_key
    ~/.wasilah_tiktok_client_secret
"""
import base64, hashlib, http.server, json, os, secrets, socket, sys, threading
import urllib.parse, urllib.request, webbrowser

AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
KEY_FILE = os.path.expanduser("~/.wasilah_tiktok_client_key")
SECRET_FILE = os.path.expanduser("~/.wasilah_tiktok_client_secret")
WEB_REDIRECT = "https://wasilah.site/tiktok/callback/"
# video.publish is direct-to-profile posting, which is what the cron needs.
# video.upload only reaches the user's inbox as a draft and would still require a
# human to tap post, so it is not enough on its own.
SCOPES = "user.info.basic,video.publish,video.upload"


def read(path, label):
    if not os.path.exists(path):
        sys.exit(f"missing {path}\nPut the {label} from the TikTok app there, then re-run.")
    v = open(path).read().strip()
    if not v:
        sys.exit(f"{path} is empty")
    return v


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
                else f"<h2>Failed: {Catcher.result.get('error_description', 'no code returned')}</h2>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *a):
        pass


def exchange(client_key, client_secret, code, redirect_uri, verifier):
    body = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if verifier:
        body["code_verifier"] = verifier
    req = urllib.request.Request(
        TOKEN, data=urllib.parse.urlencode(body).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    manual = "--manual" in sys.argv
    client_key = read(KEY_FILE, "client key")
    client_secret = read(SECRET_FILE, "client secret")
    state = secrets.token_urlsafe(16)

    # PKCE. Required for the desktop flow, harmless for web, so it is always sent.
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")

    if manual:
        redirect_uri = WEB_REDIRECT
        httpd = None
    else:
        port = free_port()
        redirect_uri = f"http://127.0.0.1:{port}/"
        httpd = http.server.HTTPServer(("127.0.0.1", port), Catcher)

    url = AUTH + "?" + urllib.parse.urlencode({
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    print(f"redirect_uri in use: {redirect_uri}")
    print("This exact string must be registered on the TikTok app, character for character.\n")

    if manual:
        print("Open this, approve, then paste the FULL URL you land on:\n")
        print(url + "\n")
        landed = input("landed URL: ").strip()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query)
        got = {k: v[0] for k, v in q.items()}
    else:
        print("Opening the browser. Approve access for the Wasilah account.\n")
        webbrowser.open(url)
        httpd.serve_forever()
        got = Catcher.result

    if got.get("state") != state:
        sys.exit("state mismatch, aborting. Re-run rather than trusting this response.")
    if "code" not in got:
        sys.exit(f"no authorization code returned: {got}")

    tok = exchange(client_key, client_secret, got["code"], redirect_uri, verifier)
    if "refresh_token" not in tok:
        sys.exit(f"token exchange failed: {tok}")

    print("\nPaste these into the wasilah-ig-scheduler repo secrets. Do not paste them"
          "\ninto a chat, a file, or a commit.\n")
    print(f"TT_CLIENT_KEY      {client_key}")
    print(f"TT_CLIENT_SECRET   {client_secret}")
    print(f"TT_REFRESH_TOKEN   {tok['refresh_token']}")
    print(f"\nscopes granted: {tok.get('scope')}")
    print(f"refresh token expires in: {tok.get('refresh_expires_in')} seconds")
    if "video.publish" not in (tok.get("scope") or ""):
        print("\nWARNING: video.publish was NOT granted. run_tiktok.py cannot post "
              "publicly without it. Check the app's approved scopes.")


if __name__ == "__main__":
    main()
