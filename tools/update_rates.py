#!/usr/bin/env python3
"""Keeps data/rates.json up to date with gold and silver prices. Standard library only.

  python tools/update_rates.py demo
      Make 120 days of SAMPLE prices. The site shows a "sample prices" banner.

  python tools/update_rates.py fetch [--skip-if-no-key]
      Get the world gold and silver price now and work out every city's rate
      (premium_percent / silver_premium_percent + city offsets).
      Feed is set by "price_feed" in config.json:
        "free"          no key: gold-api.com (live) + open.er-api.com (rupee rate, daily)
        "goldapi"       key in GOLDAPI_KEY        (2 requests per run)
        "metalpriceapi" key in METALPRICEAPI_KEY  (1 request per run; free plan is daily only)
      Runs 3 times a day. Each run is kept in that day's "u" (updates) list,
      and the day's main price is always the latest one.

  python tools/update_rates.py set chennai 14226
  python tools/update_rates.py set chennai 14226 13040 10667 --date 2026-10-30
      Type in a gold rate yourself (24K, and optionally 22K and 18K) per gram.

  python tools/update_rates.py set-silver chennai 210000 [--date 2026-10-30]
      Type in a silver rate yourself, per kg.

  python tools/update_rates.py calibrate 14226
  python tools/update_rates.py calibrate-silver 210000
      One-time: give today's local 24K gold rate per gram (or silver per kg)
      and it sets the premium in config.json so fetched prices match your market.

The first real price (fetch or set) clears the sample data automatically.
Each day's entry: {"d", "k24", "k22", "k18", "s" (silver Rs per kg), "u": [updates]}.
"""
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
RATES_FILE = ROOT / "data" / "rates.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
GRAMS_PER_TROY_OUNCE = 31.1034768
KEEP_DAYS = 400
PRICE_KEYS = ("k24", "k22", "k18", "s")


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def today_ist():
    return dt.datetime.now(IST).date()


def now_ist_hhmm():
    return dt.datetime.now(IST).strftime("%H:%M")


def now_ist_iso():
    return dt.datetime.now(IST).replace(microsecond=0).isoformat()


def from_24k(k24):
    """22K = 22/24 of 24K and 18K = 18/24 of 24K, rounded down to the rupee."""
    return math.floor(k24 * 22 / 24), math.floor(k24 * 18 / 24)


def upsert(rates, slug, day, at=None, **prices):
    """Merge prices into one day's entry for a city, keeping the list newest first.

    `prices` can hold k24 (22K/18K are worked out if not given), k22, k18 and s.
    Prices not given keep that day's earlier value, so a gold-only entry
    doesn't wipe the day's silver price.
    `at` ("HH:MM", India time) also records this as one of the day's updates.
    """
    if "k24" in prices:
        d22, d18 = from_24k(prices["k24"])
        prices.setdefault("k22", d22)
        prices.setdefault("k18", d18)
    old = rates["cities"].get(slug, [])
    same_day = next((e for e in old if e["d"] == day.isoformat()), {})
    entry = {"d": day.isoformat()}
    for key in PRICE_KEYS:
        value = prices.get(key, same_day.get(key))
        if value is not None:
            entry[key] = int(value)
    updates = [u for u in same_day.get("u", []) if u["t"] != at]
    if at:
        updates.append({"t": at, **{k: entry[k] for k in PRICE_KEYS if k in entry}})
        updates.sort(key=lambda u: u["t"])
    if updates:
        entry["u"] = updates
    hist = [e for e in old if e["d"] != day.isoformat()]
    hist.append(entry)
    hist.sort(key=lambda e: e["d"], reverse=True)
    rates["cities"][slug] = hist[:KEEP_DAYS]


def real_rates():
    """Current rates file, but emptied first if it still holds sample data."""
    rates = load_json(RATES_FILE, {"sample": False, "cities": {}})
    if rates.get("sample"):
        print("Removing the sample data: from now on only real prices are kept.")
        rates = {"sample": False, "cities": {}}
    return rates


# ---------- price feeds: each returns (gold 24K Rs/gram, silver Rs/gram) ----------

def api_key(cfg, quiet=False):
    if cfg["price_feed"] == "free":
        return "no-key-needed"
    name = {"goldapi": "GOLDAPI_KEY", "metalpriceapi": "METALPRICEAPI_KEY"}[cfg["price_feed"]]
    key = os.environ.get(name, "").strip()
    if not key and not quiet:
        sys.exit(f"{name} is not set. Get a free key from {cfg['price_feed']}, then:\n"
                 f"  PowerShell:  $env:{name} = \"your-key\"\n"
                 f"  GitHub:      Settings > Secrets and variables > Actions > {name}")
    return key


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "gold-rates-site/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        sys.exit(f"Price feed said {err.code}: {err.read()[:300].decode('utf-8', 'replace')}")


def goldapi_per_gram(key, metal):
    data = get_json(f"https://www.goldapi.io/api/{metal}/INR",
                    {"x-access-token": key, "Content-Type": "application/json"})
    per_gram = data.get("price_gram_24k")
    if not per_gram and data.get("price"):
        per_gram = data["price"] / GRAMS_PER_TROY_OUNCE
    if not per_gram:
        sys.exit(f"GoldAPI reply had no {metal} price: {data}")
    return float(per_gram)


def metalpriceapi_parse(data):
    """(gold, silver) in Rs per gram from a metalpriceapi /v1/latest reply with base USD.

    Documented shape: {"success": true, "base": "USD", "rates": {"INR": 95.2, "XAU": 0.000257,
    "USDXAU": 3879.6, ...}}. A plain key is units per 1 USD (XAU = ounces per dollar); a "USD"+key
    is the reverse (USDXAU = dollars per ounce). Errors come back as
    {"success": false, "error": {"code": 102, "info": "..."}}.
    """
    if not data.get("success"):
        err = data.get("error") or {}
        sys.exit(f"metalpriceapi error {err.get('code')}: {err.get('info') or data}")
    rates = data.get("rates") or {}
    inr_per_usd = rates.get("INR")
    if not inr_per_usd:
        sys.exit(f"metalpriceapi reply had no INR rate: {data}")
    out = []
    for metal in ("XAU", "XAG"):
        usd_per_ounce = rates.get(f"USD{metal}") or (1 / rates[metal] if rates.get(metal) else None)
        if not usd_per_ounce:
            sys.exit(f"metalpriceapi reply had no {metal} price: {data}")
        out.append(usd_per_ounce * inr_per_usd / GRAMS_PER_TROY_OUNCE)
    return tuple(out)


def metalpriceapi_per_gram(key):
    # Base stays USD (the documented default), and the key goes in a header so it never shows in logs.
    data = get_json("https://api.metalpriceapi.com/v1/latest?base=USD&currencies=INR,XAU,XAG",
                    {"X-API-KEY": key})
    return metalpriceapi_parse(data)


def free_per_gram():
    """No key needed: live gold and silver in US dollars per ounce from gold-api.com,
    and the dollar-to-rupee rate (updated once a day) from open.er-api.com."""
    usd = {}
    for metal in ("XAU", "XAG"):
        data = get_json(f"https://api.gold-api.com/price/{metal}")
        if not data.get("price") or data.get("currency", "USD") != "USD":
            sys.exit(f"gold-api.com reply had no {metal} price in USD: {data}")
        usd[metal] = float(data["price"])
    fx = get_json("https://open.er-api.com/v6/latest/USD")
    inr = (fx.get("rates") or {}).get("INR") if fx.get("result", "success") == "success" else None
    if not inr:
        sys.exit(f"open.er-api.com reply had no INR rate: {fx}")
    return tuple(usd[m] * inr / GRAMS_PER_TROY_OUNCE for m in ("XAU", "XAG"))


def fetch_world(cfg):
    if cfg["price_feed"] == "free":
        return free_per_gram()
    key = api_key(cfg)
    if cfg["price_feed"] == "goldapi":
        return goldapi_per_gram(key, "XAU"), goldapi_per_gram(key, "XAG")
    return metalpriceapi_per_gram(key)


# ---------- commands ----------

def cmd_fetch(cfg, args):
    if "--skip-if-no-key" in args and not api_key(cfg, quiet=True):
        print("No price feed key yet - keeping the current prices.")
        return
    gold, silver = fetch_world(cfg)
    rates = real_rates()
    day, at = today_ist(), now_ist_hhmm()
    gold_base = gold * (1 + cfg["premium_percent"] / 100)
    silver_kg = silver * 1000 * (1 + cfg["silver_premium_percent"] / 100)
    for city in cfg["cities"]:
        upsert(rates, city["slug"], day, at=at,
               k24=round(gold_base) + int(city.get("offset", 0)),
               s=round(silver_kg, -2) + int(city.get("silver_offset", 0)))
    rates["updated"] = now_ist_iso()
    save_json(RATES_FILE, rates)
    print(f"{day} {at}: gold 24K Rs {round(gold_base):,}/g, silver Rs {round(silver_kg, -2):,.0f}/kg "
          f"for {len(cfg['cities'])} cities")


def take_date(args):
    if "--date" in args:
        i = args.index("--date")
        return dt.date.fromisoformat(args[i + 1]), args[:i] + args[i + 2:]
    return today_ist(), args


def check_city(cfg, slug):
    if slug not in {c["slug"] for c in cfg["cities"]}:
        sys.exit(f"Unknown city '{slug}'. Add it to config.json first.")
    return slug


def number(text):
    return int(text.replace(",", ""))


def save_one(slug, day, **prices):
    rates = real_rates()
    upsert(rates, slug, day, at=now_ist_hhmm() if day == today_ist() else None, **prices)
    rates["updated"] = now_ist_iso()
    save_json(RATES_FILE, rates)
    e = next(x for x in rates["cities"][slug] if x["d"] == day.isoformat())
    print(f"Saved {slug} {day}: " + "  ".join(f"{k} {e[k]}" for k in PRICE_KEYS if k in e))


def cmd_set(cfg, args):
    day, args = take_date(args)
    if len(args) not in (2, 4):
        sys.exit("Use: set <city> <24K> [<22K> <18K>] [--date YYYY-MM-DD]")
    slug = check_city(cfg, args[0].lower())
    nums = dict(zip(("k24", "k22", "k18"), map(number, args[1:])))
    save_one(slug, day, **nums)


def cmd_set_silver(cfg, args):
    day, args = take_date(args)
    if len(args) != 2:
        sys.exit("Use: set-silver <city> <price per kg> [--date YYYY-MM-DD]")
    save_one(check_city(cfg, args[0].lower()), day, s=number(args[1]))


def cmd_calibrate(cfg, args, metal):
    if len(args) != 1:
        sys.exit(f"Use: {'calibrate' if metal == 'gold' else 'calibrate-silver'} <your local rate today>")
    local = number(args[0])
    gold, silver = fetch_world(cfg)
    if metal == "gold":
        cfg["premium_percent"] = round((local / gold - 1) * 100, 2)
        print(f"World Rs {gold:,.2f}/g, local Rs {local:,}/g -> premium_percent = {cfg['premium_percent']}")
    else:
        cfg["silver_premium_percent"] = round((local / (silver * 1000) - 1) * 100, 2)
        print(f"World Rs {silver * 1000:,.0f}/kg, local Rs {local:,}/kg -> "
              f"silver_premium_percent = {cfg['silver_premium_percent']}")
    save_json(CONFIG_FILE, cfg)


def walk(rng, days, start, drift, spread, still=0.18, step=1):
    price, out = float(start), []
    for _ in days:
        if rng.random() > still:
            price += rng.gauss(drift, spread)
        out.append(round(price / step) * step)
    return out


def cmd_demo(cfg):
    """Sample prices only, so the design can be seen before a real feed is set up."""
    rng = random.Random(30)
    city_gap = {"mumbai": -15, "pune": -15, "delhi": -12, "kolkata": -15, "bengaluru": -15,
                "hyderabad": -15, "kerala": -15, "ahmedabad": -10, "jaipur": -10}
    silver_gap = {"mumbai": -5000, "pune": -5000, "delhi": -5000, "kolkata": -5000, "bengaluru": -5000,
                  "ahmedabad": -5000, "jaipur": -5000}
    end = today_ist()
    days = [end - dt.timedelta(days=i) for i in range(119, -1, -1)]
    gold = walk(rng, days, 12900, 11, 85)
    silver = walk(rng, days, 192000, 160, 1900, still=0.3, step=100)
    rates = {"sample": True, "updated": now_ist_iso(), "cities": {}}
    for city in cfg["cities"]:
        g, s = city_gap.get(city["slug"], 0), silver_gap.get(city["slug"], 0)
        for day, gp, sp in zip(days, gold, silver):
            upsert(rates, city["slug"], day, k24=gp + g, s=sp + s)
        # Today's three updates: the last one is the day's price.
        for at, gm, sm in (("10:00", -55, -1000), ("14:00", 20, 500), ("18:00", 0, 0)):
            upsert(rates, city["slug"], end, at=at, k24=gold[-1] + g + gm, s=silver[-1] + s + sm)
    save_json(RATES_FILE, rates)
    print(f"Wrote sample data for {len(cfg['cities'])} cities, {len(days)} days.")


def main():
    cfg = load_json(CONFIG_FILE, None)
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    commands = {
        "demo": lambda: cmd_demo(cfg),
        "fetch": lambda: cmd_fetch(cfg, args),
        "set": lambda: cmd_set(cfg, args),
        "set-silver": lambda: cmd_set_silver(cfg, args),
        "calibrate": lambda: cmd_calibrate(cfg, args, "gold"),
        "calibrate-silver": lambda: cmd_calibrate(cfg, args, "silver"),
    }
    if cmd not in commands:
        sys.exit(__doc__)
    commands[cmd]()


if __name__ == "__main__":
    main()
