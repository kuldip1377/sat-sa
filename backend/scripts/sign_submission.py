#!/usr/bin/env python3
"""Print the X-SATSA-Signature header value for a submission file.

Usage:  SATSA_SIGNING_KEY=... python3 sign_submission.py submission.csv
"""
import hashlib
import hmac
import os
import sys

key = os.environ.get("SATSA_SIGNING_KEY", "")
if not key:
    sys.exit("set SATSA_SIGNING_KEY first")
with open(sys.argv[1], "rb") as f:
    print(hmac.new(key.encode(), f.read(), hashlib.sha256).hexdigest())
