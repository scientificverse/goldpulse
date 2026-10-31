#!/usr/bin/env python3
"""Daily health check for the live Gold Pulse site. Standard library only.

  python tools/daily_check.py
  python tools/daily_check.py --ref-24k 13888 --ref-silver 200000

The reference rates are today's local Chennai market rates (24K gold per gram,
silver per kg), taken from a trusted rate board. Without them the price-gap check
is skipped.

Prints one line per check (OK / WARN / FAIL), then:
  STATUS: OK | WARN | FAIL
  ACTION: <what to do>   (zero or more lines)
Exit code is always 0 so a scheduler can read the report.
"""
import datetime as dt
import json
import math
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SITE = "goldpulse.co.in"
REPO = "scientificverse/goldpulse"
RAW_RATES = f"https://raw.githubusercontent.com/{REPO}/main/data/rates.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
GOLD_TOLERANCE = 2.0     # % gap from the market before we recalibrate
SILVER_TOLERANCE = 3.0

results = []   # (level, message)
actions = []


def inr(n):
    """Indian grouping: 200000 -> 2,00,000."""
    s = str(int(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts) + "," + tail


def report(level, msg):
    results.append((level, msg))


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "goldpulse-daily-check/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def site_base():
    """https if the certificate works, otherwise http."""
    try:
        status, _ = fetch(f"https://{SITE}/")
        if status == 200:
            report("OK", "HTTPS works (padlock)")
            return f"https://{SITE}"
    except Exception as err:  # noqa: BLE001 - any failure means "not ready"
        report("WARN", f"HTTPS not working yet ({type(err).__name__}); using http. Tick 'Enforce HTTPS' on GitHub when it is ready")
    return f"http://{SITE}"


def check_pages(base):
    try:
        _, xml_text = fetch(f"{base}/sitemap.xml")
        urls = [loc.text for loc in ET.fromstring(xml_text).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    except Exception as err:  # noqa: BLE001
        report("FAIL", f"Could not read the sitemap: {err}")
        return
    bad = []
    for url in urls:
        url = url.replace(f"https://{SITE}", base)
        try:
            status, _ = fetch(url)
            if status != 200:
                bad.append(f"{url} ({status})")
        except Exception as err:  # noqa: BLE001
            bad.append(f"{url} ({err})")
    if bad:
        report("FAIL", f"{len(bad)} of {len(urls)} pages did not open: " + "; ".join(bad[:5]))
    else:
        report("OK", f"All {len(urls)} pages in the sitemap open")


def check_data(today):
    try:
        _, text = fetch(RAW_RATES)
        rates = json.loads(text)
    except Exception as err:  # noqa: BLE001
        report("FAIL", f"Could not read data/rates.json from GitHub: {err}")
        return None
    if rates.get("sample"):
        report("FAIL", "The site still has SAMPLE prices")
        return None
    chennai = (rates.get("cities") or {}).get("chennai") or []
    if not chennai:
        report("FAIL", "No Chennai prices in rates.json")
        return None
    e = chennai[0]
    if e["d"] != today:
        report("FAIL", f"Latest prices are dated {e['d']}, not today ({today})")
        actions.append("REFETCH")
    else:
        times = ", ".join(u["t"] for u in e.get("u", [])) or "none"
        report("OK", f"Prices are dated today ({today}); today's updates at {times} IST")
        if len(e.get("u", [])) < 3:
            report("WARN", f"Only {len(e.get('u', []))} of 3 updates ran today")
    ok22 = e["k22"] == math.floor(e["k24"] * 22 / 24)
    ok18 = e["k18"] == math.floor(e["k24"] * 18 / 24)
    if ok22 and ok18:
        report("OK", f"Chennai 24K ₹{inr(e['k24'])}/g, 22K ₹{inr(e['k22'])}/g, 18K ₹{inr(e['k18'])}/g (22K and 18K match the 24K rate)")
    else:
        report("FAIL", f"Carat maths is off: {e}")
    if not 5000 < e["k24"] < 50000:
        report("FAIL", f"24K ₹{inr(e['k24'])}/g looks impossible")
    if "s" in e and not 50000 < e["s"] < 1000000:
        report("FAIL", f"Silver ₹{inr(e['s'])}/kg looks impossible")
    elif "s" in e:
        report("OK", f"Chennai silver ₹{inr(e['s'])}/kg")
    return e


def check_live_page(base, entry, today_long):
    try:
        _, html = fetch(f"{base}/gold-rate-chennai.html")
    except Exception as err:  # noqa: BLE001
        report("FAIL", f"Chennai page did not open: {err}")
        return
    if "sample-note" in html:
        report("FAIL", "Live Chennai page still shows the 'Sample prices' note")
    m = re.search(r"<title>Gold Rate Today in Chennai \(([^)]+)\)", html)
    if not m or m.group(1) != today_long:
        report("FAIL", f"Live Chennai page shows date {m.group(1) if m else '?'}, expected {today_long}")
        actions.append("REBUILD")
    else:
        report("OK", f"Live Chennai page shows today's date ({today_long})")
    if entry:
        shown = re.findall(r'class="amt"><span data-g="([\d.]+)"', html)
        if shown and abs(float(shown[0]) - entry["k24"]) > 0.5:
            report("FAIL", f"Live page shows 24K ₹{float(shown[0]):,.0f}/g but data says ₹{inr(entry['k24'])}/g")
            actions.append("REBUILD")
        elif shown:
            report("OK", "Live page prices match the saved data")


def check_actions(today):
    try:
        _, text = fetch(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=10")
        runs = json.loads(text).get("workflow_runs", [])
    except Exception as err:  # noqa: BLE001
        report("WARN", f"Could not read GitHub Actions runs: {err}")
        return
    todays = [r for r in runs if dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(IST).date().isoformat() == today]
    failed = [r for r in todays if r.get("conclusion") == "failure"]
    latest = runs[0] if runs else None
    if latest and latest.get("conclusion") == "failure":
        report("FAIL", f"The latest GitHub run failed: {latest['html_url']}")
        actions.append("REFETCH")
    elif failed:
        report("OK", f"GitHub runs today: {len(todays)}; {len(failed)} failed earlier but the latest one succeeded")
    else:
        report("OK", f"GitHub runs today: {len(todays)}, none failed")


def check_reference(entry, ref24, ref_silver):
    if not entry:
        return
    if ref24:
        gap = (entry["k24"] - ref24) / ref24 * 100
        level = "OK" if abs(gap) <= GOLD_TOLERANCE else "WARN"
        report(level, f"24K vs market: ours ₹{inr(entry['k24'])} vs market ₹{ref24:,} ({gap:+.2f}%, limit ±{GOLD_TOLERANCE}%)")
        if level == "WARN":
            actions.append(f"RECALIBRATE_GOLD {ref24}")
    if ref_silver and "s" in entry:
        gap = (entry["s"] - ref_silver) / ref_silver * 100
        level = "OK" if abs(gap) <= SILVER_TOLERANCE else "WARN"
        report(level, f"Silver vs market: ours ₹{inr(entry['s'])} vs market ₹{inr(ref_silver)} ({gap:+.2f}%, limit ±{SILVER_TOLERANCE}%)")
        if level == "WARN":
            actions.append(f"RECALIBRATE_SILVER {ref_silver}")


def number_arg(name):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1].replace(",", ""))
    return None


def main():
    now = dt.datetime.now(IST)
    today = now.date().isoformat()
    today_long = f"{now.day} {now.strftime('%b %Y')}"
    print(f"Gold Pulse daily check, {today_long} {now.strftime('%I:%M %p')} IST")
    base = site_base()
    check_pages(base)
    entry = check_data(today)
    check_live_page(base, entry, today_long)
    check_actions(today)
    check_reference(entry, number_arg("--ref-24k"), number_arg("--ref-silver"))
    for level, msg in results:
        print(f"{level:4}  {msg}")
    status = "FAIL" if any(lv == "FAIL" for lv, _ in results) else "WARN" if any(lv == "WARN" for lv, _ in results) else "OK"
    print(f"STATUS: {status}")
    for a in dict.fromkeys(actions):
        print(f"ACTION: {a}")


if __name__ == "__main__":
    main()
