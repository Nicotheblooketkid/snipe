import os
import asyncio
import requests
import itertools
import random
import time
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_FILE = "usernames.txt"
WORKERS = 40
BATCH_SIZE = 500

COOKIES = {
    "datr": "S_i0aVImhfb5PBEZ3FYoKmuc",
    "fs": "FqCc1OmW08ADFgYYDjZPTnBtOWFfTU42Sm5BFqjop5sNAA%3D%3D",
    "locale": "en_US",
}

IDENTITY_ID = "1048827171645770"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
CLAIM_URL = "https://accountscenter.meta.com/api/graphql/"
CLAIM_DOC_ID = "9672408826128267"

# ── COLORS ───────────────────────────────────────────────────────────────────
RESET  = "\033[0m";  BOLD = "\033[1m";  DIM = "\033[2m"
RED    = "\033[91m"; GREEN = "\033[92m"; CYAN = "\033[96m"

# ── CLAIM SESSIONS ───────────────────────────────────────────────────────────
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

# ── TOKENS ───────────────────────────────────────────────────────────────────
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
        print("  [Tokens] Could not extract tokens")
        return None, None
    except Exception as e:
        print(f"  [Tokens] Error: {e}")
        return None, None

# ── CLAIM ─────────────────────────────────────────────────────────────────────
def claim_username(username):
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
            print(f"  {GREEN}{BOLD}[Claim] SUCCESS - @{username} claimed!{RESET}")
            return True
        err = fxim.get("error") or (data.get("errors") or [{}])[0].get("message", "unknown")
        print(f"  [Claim] Failed @{username}: {err}")
        return False
    except Exception as e:
        print(f"  [Claim] Error @{username}: {e}")
        return False

def send_webhook(username, claimed):
    if not WEBHOOK_URL:
        return
    msg = f"🎯 **CLAIMED:** `@{username}`" if claimed else f"✅ **Available (claim failed):** `@{username}`"
    try:
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
    except Exception:
        pass

# ── CHECKING ──────────────────────────────────────────────────────────────────
def cap_variants(name):
    seen = {name}
    yield name
    for v in {name.lower(), name.upper(), name.capitalize()}:
        if v not in seen: seen.add(v); yield v
    if len(name) <= 6:
        for bits in itertools.product([0, 1], repeat=len(name)):
            v = "".join(name[i].upper() if bits[i] else name[i].lower() for i in range(len(name)))
            if v not in seen: seen.add(v); yield v

def single_check(session, variant):
    try:
        r = session.get(
            f"https://horizon.meta.com/profile/{variant}/",
            allow_redirects=False, timeout=10
        )
        if r.status_code == 200: return "TAKEN"
        if r.status_code in (301, 302):
            return "AVAILABLE" if r.headers.get("Location", "") == "https://horizon.meta.com/" else "TAKEN"
    except:
        pass
    return None

def check_username(idx, name, total):
    name = name.strip().lstrip("@")
    if not name: return idx, name, "SKIP"
    s = requests.Session()
    if single_check(s, name) == "TAKEN": return idx, name, "TAKEN"
    if single_check(s, name) == "AVAILABLE":
        for v in cap_variants(name):
            if v != name and single_check(s, v) == "TAKEN": return idx, name, "TAKEN"
        return idx, name, "AVAILABLE"
    for v in cap_variants(name):
        if v != name and single_check(s, v) == "TAKEN": return idx, name, "TAKEN"
    return idx, name, "AVAILABLE"

# ── FILE IO ───────────────────────────────────────────────────────────────────
def load_usernames():
    try:
        with open(INPUT_FILE, encoding="utf-8") as f:
            lines = [l.strip().lstrip("@") for l in f if l.strip() and not l.strip().startswith("#")]
        random.shuffle(lines)
        return lines
    except FileNotFoundError:
        print(f"!! {INPUT_FILE} not found !!")
        return []

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{CYAN}{BOLD}Meta Horizon Username Checker + Claimer{RESET}\n")

    available_names = []
    claimed_names   = []
    cycle = 0

    while True:
        cycle += 1
        print(f"\n━━━ Cycle {cycle} ━━━")
        usernames = load_usernames()
        if not usernames:
            print("No usernames → sleeping 10 min...")
            time.sleep(600)
            continue

        total   = len(usernames)
        results = {}
        seen    = set()
        batches = [usernames[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

        for bnum, batch in enumerate(batches, 1):
            print(f"  Batch {bnum}/{len(batches)}")
            offset = (bnum - 1) * BATCH_SIZE
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futures = {
                    ex.submit(check_username, offset + i, name, total): name
                    for i, name in enumerate(batch)
                    if name.lower() not in seen and not seen.add(name.lower())
                }
                for fut in as_completed(futures):
                    try:
                        idx, name, status = fut.result()
                        results[idx] = (name, status)
                        prefix = f"{DIM}[{idx+1:04d}/{total:04d}]{RESET} {name:<22}"

                        if status == "TAKEN":
                            print(f"{prefix} {RED}{BOLD}taken{RESET}")
                        elif status == "AVAILABLE":
                            print(f"{prefix} {GREEN}{BOLD}available → claiming now!{RESET}")
                            available_names.append(name)
                            success = claim_username(name)
                            send_webhook(name, success)
                            if success:
                                claimed_names.append(name)
                            time.sleep(2)
                    except Exception as e:
                        print(f"Thread failed: {e}")

        taken_list = [n for n, s in results.values() if s == "TAKEN"]
        avail_list = [n for n, s in results.values() if s == "AVAILABLE"]

        with open("available.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(avail_list) + "\n" if avail_list else "")
        with open("claimed.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(claimed_names) + "\n" if claimed_names else "")

        print(f"\nCycle {cycle} done → taken: {len(taken_list)} | available: {len(avail_list)} | claimed: {len(claimed_names)}")
        print("Sleeping 5 seconds...\n")
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
