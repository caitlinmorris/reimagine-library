"""
contribute.py -- the "contribution desk" for the community library.

A small local web page where someone adds what they can teach, or what they 
know about the community. Appends to contributions.csv using proper CSV escaping 
(commas and quotes in the text are safe). librarian.py reads the CSV fresh on every 
question, so a new contribution is queryable immediately with no need for restart.
No install dependencies.

Usage:
    python3 contribute.py            # serves on http://localhost:8080
    python3 contribute.py 8090       # different port

Note: binds to localhost by default.
"""

import csv
import html
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

CSV_PATH = "contributions.csv"
BIND = "localhost"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Community Library — Contribution Desk</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 620px; margin: 3rem auto;
         padding: 0 1rem; line-height: 1.5; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  .count {{ color: #666; font-size: 0.95rem; }}
  label {{ display: block; margin-top: 1.2rem; font-weight: bold; }}
  input[type=text], textarea {{ width: 100%; padding: 0.5rem;
         font: inherit; border: 1px solid #999; box-sizing: border-box; }}
  textarea {{ height: 9rem; }}
  .consent {{ background: #f5f2ea; padding: 0.8rem 1rem; margin-top: 1.2rem;
         font-size: 0.95rem; border-left: 3px solid #b8a24a; }}
  button {{ margin-top: 1.2rem; padding: 0.6rem 1.6rem; font: inherit;
         background: #2d4a2d; color: white; border: none; cursor: pointer; }}
  .ok {{ background: #eef5ee; padding: 1rem; border-left: 3px solid #2d4a2d;
         margin-top: 1rem; }}
</style></head><body>
<h1>What can you share with the community?</h1>
<p class="count">The shelf currently holds {count} contributions.</p>
<form method="post" action="/">
  <label for="name">Your name</label>
  <input type="text" id="name" name="name" required maxlength="60">
  <label for="contribution">What you can teach or share</label>
  <textarea id="contribution" name="contribution" required
    maxlength="4000"
    placeholder="A skill, some knowledge, detailed instructions."></textarea>
  <div class="consent">
    By adding this, you agree it may be read back to community members
    who ask, possibly with your name attached depending on the community rules. 
    You can withdraw it at any time by asking a library steward to remove your row. 
    Removal is immediate and complete.
  </div>
  <button type="submit">Add to the shelf</button>
</form>
{message}
</body></html>"""

OK_MSG = """<div class="ok"><strong>Added.</strong> {name}'s contribution is
on the shelf and can be found by the librarian right now. Contribution
number {n}.</div>"""


def read_count():
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            return sum(1 for _ in csv.DictReader(f))
    except FileNotFoundError:
        return 0


def next_id():
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            ids = [int(r["id"]) for r in csv.DictReader(f) if r["id"].isdigit()]
        return max(ids) + 1 if ids else 1
    except FileNotFoundError:
        return 1


def append_row(name, contribution):
    """csv.writer handles quoting, so commas/quotes/newlines in the text
    can't corrupt the file."""
    new = next_id()
    exists = read_count() > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["id", "name", "contribution"])
        w.writerow([new, name, contribution])
    return new


class Desk(BaseHTTPRequestHandler):
    def _send(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(PAGE.format(count=read_count(), message=""))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        name = fields.get("name", [""])[0].strip()[:60]
        contribution = fields.get("contribution", [""])[0].strip()[:4000]
        if not name or not contribution:
            self._send(PAGE.format(count=read_count(), message=""))
            return
        n = append_row(name, contribution)
        msg = OK_MSG.format(name=html.escape(name), n=n)
        self._send(PAGE.format(count=read_count(), message=msg))

    def log_message(self, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    print(f"Contribution desk open at http://{BIND}:{PORT}")
    print(f"Writing to {CSV_PATH} — the librarian sees new entries "
          f"on its next question.")
    HTTPServer((BIND, PORT), Desk).serve_forever()
