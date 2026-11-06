#!/usr/bin/env python3
"""Pines team-screen relay (runs on the Pi as pines-relay.service).

Every minute: read the local /api/team, and when it changed, encrypt it and
upload it to team.enc in the pines-team-feed GitHub repo, where the Roku
channel reads it. Needs /etc/pines-relay.conf (written by install.sh):

    TOKEN=<fine-grained GitHub token, Contents read/write on the repo>
    KEY=<64 hex chars, AES-256 key shared with the Roku channel>
    REPO=granviladmin-lab/pines-team-feed

team.enc is base64(iv || AES-256-CBC(json)), made with the openssl CLI so no
Python packages are needed beyond the standard library.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONF = os.environ.get("PINES_RELAY_CONF", "/etc/pines-relay.conf")
LOCAL = os.environ.get("PINES_RELAY_LOCAL", "http://127.0.0.1:5000/api/team")
PATH = "team.enc"
INTERVAL = 60


def log(msg):
    print(msg, flush=True)


def load_conf():
    conf = {}
    with open(CONF) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    for k in ("TOKEN", "KEY", "REPO"):
        if not conf.get(k):
            sys.exit(f"{CONF}: {k} missing")
    return conf


def encrypt(data: bytes, key_hex: str) -> str:
    iv = os.urandom(16)
    ct = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-K", key_hex, "-iv", iv.hex()],
        input=data, capture_output=True, check=True).stdout
    return base64.b64encode(iv + ct).decode()


def github(conf, method, body=None):
    url = f"https://api.github.com/repos/{conf['REPO']}/contents/{PATH}"
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    req.add_header("Authorization", f"Bearer {conf['TOKEN']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "pines-relay")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def current_sha(conf):
    try:
        return github(conf, "GET")["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    conf = load_conf()
    last = None
    sha = None
    while True:
        try:
            with urllib.request.urlopen(LOCAL, timeout=15) as r:
                data = json.load(r)
            # Weather changes on its own; the hash covers everything, so a
            # new temperature also goes out (at most once a minute).
            blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(blob).hexdigest()
            if digest != last:
                if sha is None:
                    sha = current_sha(conf)
                body = {"message": "Update team screen", "content": base64.b64encode(
                    encrypt(blob, conf["KEY"]).encode()).decode()}
                if sha:
                    body["sha"] = sha
                try:
                    sha = github(conf, "PUT", body)["content"]["sha"]
                except urllib.error.HTTPError as e:
                    if e.code in (409, 422):  # stale sha: refetch next round
                        sha = None
                    raise
                last = digest
                log("uploaded team.enc")
        except Exception as e:  # keep going through network blips
            log(f"relay error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
