import os
import asyncio
import httpx
import random
import json
import re
import uuid
import requests
import itertools
import time
from concurrent.futures import ThreadPoolExecutor

# accountscenter cookies for claiming
COOKIES = {
    "datr": "S_i0aVImhfb5PBEZ3FYoKmuc",
    "fs": "FqCc1OmW08ADFgYYDjZPTnBtOWFfTU42Sm5BFqjop5sNAA%3D%3D",
    "locale": "en_US",
}

# horizon.meta.com cookies for checking — must be logged in for accurate results
HORIZON_COOKIES = {
    "datr": "6nu1aeFl2wsX9VYD--NfQSWC",
    "locale": "en_US",
}

IDENTITY_ID = "1048827171645770"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
CONCURRENT = 5
CLAIM_URL = "https://accountscenter.meta.com/api/graphql/"
CLAIM_DOC_ID = "9672408826128267"

thread_pool = ThreadPoolExecutor(max_workers=128)

def load_usernames():
    with open("usernames.txt", encoding="utf-8") as f:
        return [x.strip().lstrip("@") for x in f if x.strip()]

def load_proxies():
    proxies = []
    try:
        with open("proxies.txt") as f:
            for line in f:
                p = line.strip()
                if not p:
                    continue
                parts = p.split(":")
                if len(parts) == 4:
                    host, port, user, password = parts
                    proxies.append(f"http://{user}:{password}@{host}:{port}")
                elif len(parts) == 2:
                    proxies.append(f"http://{parts[0]}:{parts[1]}")
    except FileNotFoundError:
        pass
    return proxies

claim_sessions = []
for _ in range(32):
    s = requests.Session()
    s.cookies.update(COOKIES)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36 Edg/145.0.0.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://accountscenter.meta.com",
        "Referer": f"https://accountscenter.meta.com/profiles/{IDENTITY_ID}/username/?entrypoint=fb_account_center",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-asbd-id": "359341",
    })
    claim_sessions.append(s)

session_index = 0

def get_claim_session():
    global session_index
    s = claim_sessions[session_index % len(claim_sessions)]
    session_index += 1
    return s

def get_fresh_tokens():
    try:
        s = get_claim_session()
        r = s.get(
            f"https://accountscenter.meta.com/profiles/{IDENTITY_ID}/username/?entrypoint=fb_account_center",
            timeout=10
        )
        html = r.text
        dtsg_match = (
            re.search(r'"token":"([^"]+)","isEncrypted"', html)
            or re.search(r'"DTSGInitialData"[^}]*"token":"([^"]+)"', html)
        )
        lsd_match = re.search(r'"LSD"[^}]*"token":"([^"]+)"', html)
        if dtsg_match and lsd_match:
            return dtsg_match.group(1), lsd_match.group(1)
        print("  [Tokens] Could not extract tokens from page")
        return None, None
    except Exception as e:
        print(f"  [Tokens] Error: {e}")
        return None, None

def claim_username_sync(username):
    fb_dtsg, lsd = get_fresh_tokens()
    if not fb_dtsg or not lsd:
        print(f"  [Claim] FAILED - no tokens for @{username}")
        return False
    payload = {
        "av": IDENTITY_ID,
        "__user": "0",
        "__a": "1",
        "fb_dtsg": fb_dtsg,
        "lsd": lsd,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "useFXIMUpdateUsernameMutation",
        "server_timestamps": "true",
        "doc_id": CLAIM_DOC_ID,
        "variables": json.dumps({
            "client_mutation_id": str(uuid.uuid4()),
            "family_device_id": "device_id_fetch_datr",
            "identity_ids": [IDENTITY_ID],
            "target_fx_identifier": IDENTITY_ID,
            "username": username,
            "interface": "FRL_WEB"
        })
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-fb-friendly-name": "useFXIMUpdateUsernameMutation",
        "x-fb-lsd": lsd,
        "x-asbd-id": "359341",
    }
    try:
        s = get_claim_session()
        r = s.post(CLAIM_URL, data=payload, headers=headers, timeout=10)
        data = r.json()
        fxim = data.get("data", {}).get("fxim_update_identity_username", {})
        if fxim.get("error") is None and "fxim_update_identity_username" in data.get("data", {}):
            print(f"  [Claim] SUCCESS - @{username} claimed!")
            return True
        err = fxim.get("error") or (data.get("errors") or [{}])[0].get("message", "unknown")
        print(f"  [Claim] Failed @{username}: {err}")
        return False
    except Exception as e:
        print(f"  [Claim] Error @{username}: {e}")
        return False

def send_webhook_sync(username, claimed):
    msg = f"🎯 **CLAIMED:** `@{username}`" if claimed else f"✅ **Available (claim failed):** `@{username}`"
    try:
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
    except Exception:
        pass

def cap_variants(name):
    seen = set()
    for combo in itertools.product([0, 1], repeat=len(name)):
        variant = "".join(
            c.upper() if combo[i] else c.lower()
            for i, c in enumerate(name)
        )
        if variant not in seen:
            seen.add(variant)
            yield variant

available_names = []
claimed_names = []

def horizon_check_sync(username):
    url = f"https://horizon.meta.com/profile/{username}"  # no trailing slash — triggers 301 for taken names
    try:
        r = requests.get(url, allow_redirects=False, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        status = r.status_code
        loc = r.headers.get("Location", "").rstrip("/").lower()
        print(f"  [DEBUG] {username} status={status} loc={loc!r}", flush=True)
        if status == 301:
            return "TAKEN"
        if status == 200:
            return "TAKEN"
        if status == 302:
            if loc in ("https://horizon.meta.com", "https://www.meta.com"):
                return "AVAILABLE"
            return "TAKEN"
        return "UNKNOWN"
    except Exception as e:
        print(f"  [DEBUG] {username} exception={e}", flush=True)
        return "UNKNOWN"

async def horizon_check(client, username):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, horizon_check_sync, username)

async def check_single_name(semaphore, client, username, i, total):
    async with semaphore:
        await asyncio.sleep(1)  # rate limit protection
        try:
            variants = list(cap_variants(username))

            # Check only lowercase — rate limit safe
            results = [await horizon_check(client, username.lower())]

            if any(r == "TAKEN" for r in results):
                print(f"[{i:>4}/{total}] @{username:<20} TAKEN")
                return

            if all(r == "UNKNOWN" for r in results):
                print(f"[{i:>4}/{total}] @{username:<20} UNKNOWN — skipping")
                return

            # Double check base name before claiming — prevents false positives
            await asyncio.sleep(2)
            recheck = await horizon_check(client, username.lower())
            if recheck != "AVAILABLE":
                print(f"[{i:>4}/{total}] @{username:<20} TAKEN")
                return
            await asyncio.sleep(1)
            recheck2 = await horizon_check(client, username.lower())
            if recheck2 != "AVAILABLE":
                print(f"[{i:>4}/{total}] @{username:<20} TAKEN")
                return

            print(f"[{i:>4}/{total}] @{username:<20} AVAILABLE — claiming now...")
            available_names.append(username)

            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(thread_pool, claim_username_sync, username)
            asyncio.ensure_future(loop.run_in_executor(thread_pool, send_webhook_sync, username, success))
            if success:
                claimed_names.append(username)

        except Exception as e:
            print(f"[{i:>4}/{total}] @{username:<20} ERROR: {e}")

async def run_cycle(names, proxies):
    semaphore = asyncio.Semaphore(CONCURRENT)
    proxy = random.choice(proxies) if proxies else None
    client_kwargs = {
        "follow_redirects": False,
        "http2": True,
        "cookies": COOKIES,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "limits": httpx.Limits(
            max_connections=200,
            max_keepalive_connections=50,
            keepalive_expiry=30,
        ),
    }
    if proxy:
        client_kwargs["proxy"] = proxy
    async with httpx.AsyncClient(**client_kwargs) as client:
        tasks = [
            check_single_name(semaphore, client, name, i, len(names))
            for i, name in enumerate(names, 1)
        ]
        await asyncio.gather(*tasks)

async def main():
    names = load_usernames()
    proxies = load_proxies()
    print(f"Loaded {len(names)} usernames | {len(proxies)} proxies | {CONCURRENT} concurrent\n")

    cycle = 1
    while True:
        print(f"--- CYCLE {cycle} ---\n")
        await run_cycle(names, proxies)
        print(f"\n--- CYCLE {cycle} COMPLETE | Available: {len(available_names)} | Claimed: {len(claimed_names)} ---")
        if claimed_names:
            print(f"  Claimed: {', '.join(claimed_names)}")
        with open("available.txt", "w") as f:
            f.write("\n".join(available_names))
        with open("claimed.txt", "w") as f:
            f.write("\n".join(claimed_names))
        cycle += 1
        print(f"\nRestarting in 5 seconds...\n")
        await asyncio.sleep(5)

asyncio.run(main())