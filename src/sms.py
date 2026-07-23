"""
src/sms.py — Sheria Yangu SMS sending: OTP (register/sign-in) + bill notifications.

Uses Africa's Talking's SMS API (one API key covers both OTP-style transactional
SMS and bulk notification SMS — see docs/api-key-setup.md for why you don't need
a separate key per use case).

Two message types, two functions:
  1. issue_otp(phone_number)              -> generates + sends a 6-digit sign-in code
  2. send_bill_notification(phone, bill)  -> sends the "a bill just opened" alert

Both go through _send_sms() so retry/error-handling/logging lives in one place.

Setup:
  pip install africastalking          (add to requirements.txt — see note below)
  .env must have AT_USERNAME and AT_API_KEY (sandbox values are fine for testing —
  sandbox never sends a real SMS, it just simulates success/failure and logs to
  your Africa's Talking dashboard's simulator).

Run a standalone test (sandbox-safe, does not need real credits):
  python src/sms.py --test-otp +254700000000
  python src/sms.py --test-notification +254700000000
"""

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY")

OTP_LENGTH = 6
OTP_VALID_MINUTES = 5

# Keep this as a single template string (mirrors the BRAND variable convention
# in the deck build script) so the wording can be tweaked in one place without
# hunting through the sending logic.
OTP_TEMPLATE = "Sheria Yangu: your sign-in code is {code}. Valid for {minutes} minutes. Do not share this code."

BILL_NOTIFICATION_TEMPLATE = (
    "Sheria Yangu: \"{bill_title}\" ({level}) is now open for public comment. "
    "Have your say before {closes_at}. Read it in plain English/Swahili: {link}"
)


@dataclass
class OtpIssued:
    phone_number: str
    code: str
    expires_at: datetime


def _get_sms_client():
    """
    Lazily imports and initialises the Africa's Talking SDK so this module can
    still be imported (e.g. for OTP_TEMPLATE/formatting logic) in contexts
    where the package isn't installed yet, such as quick unit tests.
    """
    if not AT_API_KEY:
        raise RuntimeError(
            "AT_API_KEY is not set. Copy .env.example to .env and fill in "
            "AT_USERNAME / AT_API_KEY (use 'sandbox' + your sandbox app key to "
            "test without spending real SMS credit)."
        )
    import africastalking

    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    return africastalking.SMS


AT_SMS_URL = "https://api.sandbox.africastalking.com/version1/messaging"


def _send_sms_via_curl(phone_number: str, message: str) -> dict:
    """
    Fallback path: shells out to the system's curl.exe instead of using
    requests/urllib3/the africastalking SDK.

    Why this exists: on at least one Windows machine in this project, Python's
    own TLS stack (requests -> urllib3 -> ssl) could not reliably complete a
    POST to api.sandbox.africastalking.com — it failed inconsistently with a
    read timeout, an SSL "wrong version number" error, and a DNS resolution
    error across different runs and different networks (home WiFi AND mobile
    hotspot), while `curl -v` to the same host from the same machine worked
    every time. That inconsistency (three different failure modes hitting one
    specific host, while other requests-based scrapers in this repo work fine
    against other hosts) points to something about how Python's HTTP stack
    negotiates with this particular server/CDN, not a real network outage —
    but it wasn't worth chasing further under a hackathon deadline. curl uses
    the OS's native TLS stack (schannel on Windows) instead of Python's
    bundled OpenSSL, and empirically gets through, so this function uses it
    directly as a pragmatic workaround.

    If this ALSO fails on your machine, the problem is upstream of Python
    entirely (real network/DNS outage, or the AT sandbox itself is down) —
    at that point, re-test from a different machine or wait and retry, not a
    code fix.
    """
    import json as _json
    import subprocess

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST", AT_SMS_URL,
            "-H", f"apiKey: {AT_API_KEY}",
            "-H", "Accept: application/json",
            "--data-urlencode", f"username={AT_USERNAME}",
            "--data-urlencode", f"to={phone_number}",
            "--data-urlencode", f"message={message}",
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl fallback failed (exit {result.returncode}): {result.stderr}")
    try:
        return _json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"curl fallback got a non-JSON response: {result.stdout!r}")


def _send_sms(phone_number: str, message: str) -> dict:
    """
    Sends one SMS and returns Africa's Talking's raw response dict for logging.
    Raises on transport-level failure (network/auth); a "Sent"/"Failed" per-
    recipient result inside the response is NOT raised, it's returned so the
    caller can decide how to handle a single bad number without blowing up a
    bulk notification run.

    Tries the official SDK first (the portable, correct path — this is what
    should run in the real deployed app and on any normal network). Only
    falls back to raw curl (see _send_sms_via_curl) if that raises a
    connection-level error, so this module keeps working as-is the moment
    the underlying network/TLS issue resolves itself.
    """
    import requests as _requests

    try:
        sms = _get_sms_client()
        return sms.send(message, [phone_number])
    except (_requests.exceptions.ConnectionError, _requests.exceptions.Timeout,
            _requests.exceptions.SSLError) as exc:
        print(f"[sms] SDK/requests path failed ({exc.__class__.__name__}), "
              f"retrying via curl fallback...")
        return _send_sms_via_curl(phone_number, message)


def generate_otp() -> str:
    return "".join(random.choices("0123456789", k=OTP_LENGTH))


def issue_otp(phone_number: str) -> OtpIssued:
    """
    Generates a fresh OTP and sends it by SMS. Returns the code and its
    expiry so the CALLER can store it (e.g. in the `identity` table's
    pending-verification row, or a short-lived cache) — this module doesn't
    persist anything itself, to keep it independent of whatever storage layer
    ends up backing registration/sign-in.

    Recommended storage: keep only a hash of the code (e.g. sha256) plus the
    expiry timestamp, the same way you'd never store a password in plaintext.
    A leaked OTP is short-lived, but there's no reason to store it recoverable.
    """
    code = generate_otp()
    expires_at = datetime.now() + timedelta(minutes=OTP_VALID_MINUTES)
    message = OTP_TEMPLATE.format(code=code, minutes=OTP_VALID_MINUTES)
    response = _send_sms(phone_number, message)
    print(f"[sms] OTP send response for {phone_number}: {response}")
    return OtpIssued(phone_number=phone_number, code=code, expires_at=expires_at)


def send_bill_notification(phone_number: str, bill_title: str, level: str,
                            closes_at: str, link: str) -> dict:
    """
    level: "national" or "county" — shown to the citizen so they know which
    body the bill is in front of.
    closes_at: a pre-formatted, human-readable string (e.g. "25 May 2026") —
    format it before calling this, this function doesn't parse dates.
    link: deep link into the app for this specific bill.
    """
    message = BILL_NOTIFICATION_TEMPLATE.format(
        bill_title=bill_title, level=level, closes_at=closes_at, link=link
    )
    response = _send_sms(phone_number, message)
    print(f"[sms] Notification send response for {phone_number}: {response}")
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-otp", metavar="PHONE", help="send a test OTP to this number")
    parser.add_argument("--test-notification", metavar="PHONE", help="send a test bill notification")
    args = parser.parse_args()

    if args.test_otp:
        result = issue_otp(args.test_otp)
        print(f"Generated code {result.code} (expires {result.expires_at.isoformat()}) "
              f"— in sandbox mode this is NOT a real SMS, check your AT sandbox simulator.")
    elif args.test_notification:
        send_bill_notification(
            args.test_notification,
            bill_title="Nairobi City County Finance Bill, 2026",
            level="county",
            closes_at="15 August 2026",
            link="https://sheriayangu.example/bills/nairobi-finance-2026",
        )
    else:
        parser.print_help()
        sys.exit(1)
