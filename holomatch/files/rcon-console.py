#!/usr/bin/env python3
"""Minimal RCON web console for the Holomatch (Lilium Voyager / STVEF) server.

Serves a small, password-protected web page with a command box, a confirmation
step, and a few quick-action buttons. Submitted commands are relayed to the
co-located dedicated server using the Quake 3 RCON protocol (a connectionless
UDP packet on the game port), and the server's reply is shown back in the page.

This uses only the Python standard library so it can run in a stock
``python:3-slim`` sidecar container with the script mounted from a ConfigMap --
no custom image to build or push.

Configuration (environment variables):
  RCON_HOST         Game server address (default 127.0.0.1 -- same pod).
  RCON_PORT         Game server UDP port (default 27960).
  RCON_PASSWORD     Server ``rconpassword`` (required for commands to work).
  CONSOLE_USER      HTTP Basic Auth username for the web UI (default "admin").
  CONSOLE_PASSWORD  HTTP Basic Auth password (required; blank => fail closed).
  LISTEN_ADDR       Bind address (default 0.0.0.0).
  LISTEN_PORT       Bind port (default 8090).
  RCON_TIMEOUT      Seconds to wait for the first RCON reply (default 1.5).
"""
import base64
import hmac
import html
import json
import os
import socket
import string
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

RCON_HOST = os.environ.get("RCON_HOST", "127.0.0.1")
RCON_PORT = int(os.environ.get("RCON_PORT", "27960"))
RCON_PASSWORD = os.environ.get("RCON_PASSWORD", "")
CONSOLE_USER = os.environ.get("CONSOLE_USER", "admin")
CONSOLE_PASSWORD = os.environ.get("CONSOLE_PASSWORD", "")
LISTEN_ADDR = os.environ.get("LISTEN_ADDR", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8090"))
RCON_TIMEOUT = float(os.environ.get("RCON_TIMEOUT", "1.5"))

MAX_CMD_LEN = 512
OOB = b"\xff\xff\xff\xff"  # Quake3 connectionless packet prefix

# Quick-action buttons (label -> command). These only prefill the command box;
# the operator still has to confirm before anything is sent.
QUICK_ACTIONS = [
    ("Status", "status"),
    ("Next map", "vstr nextmap"),
    ("Restart map", "map_restart"),
    ("Add bot (Tuvok, lvl 4)", "addbot tuvok 4"),
    ("Kick all bots", "kick allbots"),
]


def sanitize(command):
    """Trim, strip control characters and the 0xFF byte (which would corrupt
    the UDP datagram), and cap the length. ';' is allowed so operators can
    chain commands the way they would at the real console."""
    command = command.strip()
    command = "".join(
        ch for ch in command
        if ch >= " " and ch != "\x7f" and ord(ch) != 0xFF
    )
    return command[:MAX_CMD_LEN]


def rcon(command):
    """Send a single RCON command and return the server's textual reply."""
    if not RCON_PASSWORD:
        return "ERROR: the server rconpassword is not configured, so remote " \
               "commands are disabled. Set holomatch.rconpassword and redeploy."
    payload = OOB + b"rcon " + RCON_PASSWORD.encode() + b" " + command.encode()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(RCON_TIMEOUT)
            sock.sendto(payload, (RCON_HOST, RCON_PORT))
            chunks = []
            while True:
                try:
                    data, _ = sock.recvfrom(65536)
                except socket.timeout:
                    break
                if data.startswith(OOB):
                    data = data[len(OOB):]
                if data.startswith(b"print\n"):
                    data = data[len(b"print\n"):]
                chunks.append(data.decode("utf-8", "replace"))
                # We got the first packet; wait only briefly for any follow-ups.
                sock.settimeout(0.4)
    except OSError as exc:
        return "ERROR: could not reach the game server at %s:%d (%s)" % (
            RCON_HOST, RCON_PORT, exc)
    text = "".join(chunks).strip()
    return text or "(command sent; no output returned)"


QUICK_BUTTONS_HTML = "\n        ".join(
    '<button type="button" class="qa" data-cmd="%s">%s</button>' % (
        html.escape(cmd, quote=True), html.escape(label))
    for label, cmd in QUICK_ACTIONS
)

PAGE_TEMPLATE = string.Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Holomatch Server Console</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font-family: system-ui, sans-serif; background: #0b0f1a; color: #e8ecf4; }
  header { padding: 16px 20px; background: #131a2b; border-bottom: 1px solid #26314d; }
  header h1 { margin: 0; font-size: 18px; }
  header p { margin: 4px 0 0; color: #8aa0c6; font-size: 13px; }
  main { max-width: 820px; margin: 0 auto; padding: 20px; }
  h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em; color: #8aa0c6; }
  .qa-row { display: flex; flex-wrap: wrap; gap: 8px; }
  button { font: inherit; cursor: pointer; border-radius: 6px; border: 1px solid #33507f;
           background: #1c294a; color: #dce6fb; padding: 8px 12px; }
  button:hover { background: #24345c; }
  button.danger { border-color: #7f3333; background: #4a1c1c; color: #ffd9d9; }
  button.danger:hover { background: #5c2424; }
  form#cmdform { display: flex; gap: 8px; margin: 8px 0 4px; }
  input#command { flex: 1; font: inherit; padding: 10px 12px; border-radius: 6px;
                  border: 1px solid #33507f; background: #0e1526; color: #e8ecf4; }
  pre#output { background: #05080f; border: 1px solid #26314d; border-radius: 6px;
               padding: 12px; min-height: 120px; white-space: pre-wrap; word-break: break-word;
               overflow-x: auto; }
  dialog { background: #131a2b; color: #e8ecf4; border: 1px solid #33507f; border-radius: 8px;
           max-width: 480px; }
  dialog::backdrop { background: rgba(0,0,0,.6); }
  dialog pre { background: #05080f; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; }
  dialog menu { display: flex; justify-content: flex-end; gap: 8px; padding: 0; margin: 12px 0 0; }
</style>
</head>
<body>
<header>
  <h1>Holomatch Server Console</h1>
  <p>RCON target: $host:$port</p>
</header>
<main>
  <section>
    <h2>Quick actions</h2>
    <div class="qa-row">
        $buttons
    </div>
  </section>
  <section>
    <h2>Command</h2>
    <form id="cmdform" autocomplete="off">
      <input id="command" name="command" placeholder="e.g. map HM_BORG3" maxlength="512"
             aria-label="Console command" required>
      <button type="submit">Send&hellip;</button>
    </form>
    <p style="color:#8aa0c6;font-size:12px;margin:4px 0 0">
      Commands run on the live server. You will be asked to confirm.
    </p>
  </section>
  <section>
    <h2>Output</h2>
    <pre id="output" aria-live="polite">Ready.</pre>
  </section>
</main>
<dialog id="confirm">
  <h2 style="margin-top:0">Confirm command</h2>
  <p>Send this command to the live server?</p>
  <pre id="confirmcmd"></pre>
  <menu>
    <button type="button" id="cancel">Cancel</button>
    <button type="button" id="confirmok" class="danger">Confirm &amp; send</button>
  </menu>
</dialog>
<script src="app.js"></script>
</body>
</html>
""")

PAGE_HTML = PAGE_TEMPLATE.safe_substitute(
    host=html.escape(RCON_HOST), port=RCON_PORT, buttons=QUICK_BUTTONS_HTML,
).encode("utf-8")

APP_JS = b"""(function () {
  var form = document.getElementById('cmdform');
  var input = document.getElementById('command');
  var output = document.getElementById('output');
  var dlg = document.getElementById('confirm');
  var confirmCmd = document.getElementById('confirmcmd');

  Array.prototype.forEach.call(document.querySelectorAll('.qa'), function (b) {
    b.addEventListener('click', function () {
      input.value = b.getAttribute('data-cmd');
      input.focus();
    });
  });

  function send(command) {
    output.textContent = 'Running: ' + command + ' ...';
    fetch('api/rcon', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: command })
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (!r.ok) { output.textContent = 'Error: ' + (r.data.error || 'request failed'); return; }
      output.textContent = '> ' + r.data.command + '\\n\\n' + r.data.output;
    }).catch(function (e) { output.textContent = 'Request failed: ' + e; });
  }

  function ask(command) {
    confirmCmd.textContent = command;
    if (typeof dlg.showModal === 'function') { dlg.showModal(); }
    else if (window.confirm('Send: ' + command + ' ?')) { send(command); }
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var command = input.value.trim();
    if (command) { ask(command); }
  });
  document.getElementById('cancel').addEventListener('click', function () { dlg.close(); });
  document.getElementById('confirmok').addEventListener('click', function () {
    dlg.close();
    send(input.value.trim());
  });
})();
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "HolomatchConsole/1.0"
    protocol_version = "HTTP/1.1"

    def _security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; connect-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _unauthorized(self):
        body = b"Authentication required\n"
        self.send_response(401)
        self.send_header(
            "WWW-Authenticate", 'Basic realm="Holomatch Console", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        if not CONSOLE_PASSWORD:
            return False  # fail closed if no password is configured
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8", "replace")
        except Exception:
            return False
        user, _, password = decoded.partition(":")
        ok_user = hmac.compare_digest(user, CONSOLE_USER)
        ok_pass = hmac.compare_digest(password, CONSOLE_PASSWORD)
        if ok_user and ok_pass:
            self._user = user
            return True
        return False

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, "text/plain; charset=utf-8", b"ok")
            return
        if not self._authed():
            self._unauthorized()
            return
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE_HTML)
        elif self.path == "/app.js":
            self._send(200, "application/javascript; charset=utf-8", APP_JS)
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if not self._authed():
            self._unauthorized()
            return
        if self.path != "/api/rcon":
            self._send(404, "text/plain; charset=utf-8", b"not found\n")
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length > 4096:
            self._send(413, "text/plain; charset=utf-8", b"payload too large\n")
            return
        body = self.rfile.read(length) if length else b""
        command = ""
        ctype = self.headers.get("Content-Type", "")
        try:
            if "application/json" in ctype:
                command = (json.loads(body or b"{}").get("command") or "")
            else:
                command = parse_qs(body.decode("utf-8", "replace")).get(
                    "command", [""])[0]
        except Exception:
            self._send(400, "text/plain; charset=utf-8", b"bad request\n")
            return
        command = sanitize(command)
        if not command:
            self._send(400, "application/json; charset=utf-8",
                       json.dumps({"error": "empty command"}).encode())
            return
        # Audit trail: every executed command is logged to the container stdout.
        sys.stderr.write("[console] %s ran: %s\n" % (
            getattr(self, "_user", "?"), command))
        sys.stderr.flush()
        output = rcon(command)
        self._send(200, "application/json; charset=utf-8",
                   json.dumps({"command": command, "output": output}).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write("[console] %s - %s\n" % (
            self.address_string(), fmt % args))


def main():
    if not CONSOLE_PASSWORD:
        sys.stderr.write(
            "[console] WARNING: CONSOLE_PASSWORD is empty; refusing all "
            "requests until it is set.\n")
    if not RCON_PASSWORD:
        sys.stderr.write(
            "[console] WARNING: RCON_PASSWORD is empty; commands will not be "
            "accepted by the game server.\n")
    server = ThreadingHTTPServer((LISTEN_ADDR, LISTEN_PORT), Handler)
    sys.stderr.write("[console] listening on %s:%d -> rcon %s:%d\n" % (
        LISTEN_ADDR, LISTEN_PORT, RCON_HOST, RCON_PORT))
    server.serve_forever()


if __name__ == "__main__":
    main()
