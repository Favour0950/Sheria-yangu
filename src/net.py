"""
src/net.py — shared HTTP GET with a curl fallback.

Why this exists: on Violet's machine, Python's own requests/urllib3/ssl stack
has now failed against TWO unrelated hosts — api.sandbox.africastalking.com
(read timeouts, SSL "wrong version number") and new.mzalendo.com (SSL
"TLSV1_ALERT_INTERNAL_ERROR") — while `curl.exe` reaches both successfully
from the same machine. Two different hosts hitting the same failure pattern
means this is a local Python/TLS-stack issue, not something wrong with either
service. Since chasing the actual root cause (candidates: Python 3.14 being
very new, antivirus HTTPS inspection, or something else entirely) wasn't
resolving quickly and was blocking real work, every network call in this repo
that has hit this problem should go through this shared helper instead of
duplicating the workaround in each file (this used to be copy-pasted directly
into sms.py — see git history for that first version).

If curl ALSO fails for a given host, the problem is upstream of any code fix
here (real outage, or a host neither this stack nor curl can reach) — that's
a "wait and retry" situation, not something to keep patching around.
"""

import subprocess

import requests


def get_text(url: str, headers: dict | None = None, timeout: int = 20) -> str:
    """GET a URL as text, falling back to curl.exe if requests hits a
    connection/timeout/SSL error."""
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as exc:
        print(f"[net] requests failed ({exc.__class__.__name__}) for {url}, retrying via curl...")
        return _curl_text(url, headers, timeout)


def get_bytes(url: str, headers: dict | None = None, timeout: int = 60) -> bytes:
    """GET a URL as raw bytes (for PDF downloads), same fallback behaviour."""
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as exc:
        print(f"[net] requests failed ({exc.__class__.__name__}) for {url}, retrying via curl...")
        return _curl_bytes(url, headers, timeout)


def _curl_cmd(url: str, headers: dict | None) -> list:
    cmd = ["curl", "-s", "-L", url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    return cmd


def _curl_text(url: str, headers: dict | None, timeout: int) -> str:
    result = subprocess.run(_curl_cmd(url, headers), capture_output=True, text=True, timeout=timeout + 15)
    if result.returncode != 0:
        raise RuntimeError(f"curl fallback failed (exit {result.returncode}) for {url}: {result.stderr}")
    return result.stdout


def _curl_bytes(url: str, headers: dict | None, timeout: int) -> bytes:
    result = subprocess.run(_curl_cmd(url, headers), capture_output=True, timeout=timeout + 15)
    if result.returncode != 0:
        raise RuntimeError(f"curl fallback failed (exit {result.returncode}) for {url}: {result.stderr!r}")
    return result.stdout
