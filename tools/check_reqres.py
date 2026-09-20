"""Quick ReqRes connectivity / API-key check.

    python tools/check_reqres.py

Sends ONE POST /api/users request (uses 1 request of the daily quota) and explains the result.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

URL = os.getenv("REQRES_BASE_URL", "https://reqres.in").rstrip("/") + "/api/users"
KEY = os.getenv("REQRES_API_KEY", "")

headers = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": "orangehrm-hybrid-automation/1.0"}
if KEY:
    headers["x-api-key"] = KEY

masked = f"{KEY[:4]}...{KEY[-4:]}" if len(KEY) > 8 else ("<set but very short>" if KEY else "<not set>")
print(f"URL            : {URL}")
print(f"REQRES_API_KEY : {masked}")
if KEY and ("paste" in KEY.lower() or "your" in KEY.lower()):
    print("WARNING        : the key looks like the placeholder text, not a real key!")

request = urllib.request.Request(URL, data=json.dumps({"name": "morpheus", "job": "leader"}).encode(),
                                 headers=headers, method="POST")
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        status, body = response.status, response.read().decode(errors="replace")
except urllib.error.HTTPError as error:
    status, body = error.code, error.read().decode(errors="replace")
except Exception as error:  # network / proxy / firewall
    print(f"RESULT         : cannot reach ReqRes - {error}")
    raise SystemExit(2)

print(f"HTTP status    : {status}")
print(f"Response body  : {body[:400]}")
advice = {
    201: "OK - ReqRes works. Run: python -m pytest -m api -v",
    401: "API key rejected/missing. Fix the key, or remove it:  Remove-Item Env:REQRES_API_KEY",
    403: "API key not allowed for this call. Create/copy a valid key at https://app.reqres.in",
    429: "Rate limit. If the body says 'requests/day', wait for the reset (midnight UTC) or use a valid free API key.",
}
print(f"ADVICE         : {advice.get(status, 'Unexpected status - send this output for help.')}")
raise SystemExit(0 if status == 201 else 1)
