import requests, json, os, time
from datetime import datetime, timezone

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

with open("holdings.json") as f:
    holdings = json.load(f)

prices = {"us": {}, "pk": {}, "poke": {}, "updated": datetime.now(timezone.utc).isoformat()}

# ── US STOCKS via Finnhub ─────────────────────────────────────────────
print("Fetching US stocks...")
for h in holdings.get("us", []):
    ticker = h["ticker"]
    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}",
            timeout=10
        )
        d = r.json()
        if d.get("c") and d["c"] > 0:
            prev = d.get("pc", d["c"])
            chg  = ((d["c"] - prev) / prev * 100) if prev else 0
            prices["us"][ticker] = {"price": d["c"], "change_pct": round(chg, 2)}
            print(f"  {ticker}: ${d['c']}")
        else:
            print(f"  {ticker}: no data")
    except Exception as e:
        print(f"  {ticker}: error - {e}")
    time.sleep(0.3)

# ── PSX via Yahoo Finance ─────────────────────────────────────────────
print("Fetching PSX stocks...")
for h in holdings.get("pk", []):
    ticker = h["ticker"]
    sym    = ticker + ".KA"
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        d = r.json()
        meta  = d["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        chg   = ((price - prev) / prev * 100) if prev else 0
        prices["pk"][ticker] = {"price": price, "change_pct": round(chg, 2)}
        print(f"  {ticker}: Rs.{price}")
    except Exception as e:
        print(f"  {ticker}: error - {e}")
    time.sleep(0.3)

# ── POKEMON via PriceCharting ─────────────────────────────────────────
print("Fetching Pokemon prices...")

GRADE_MAP = {
    "PSA 10": "psa-10-price",
    "PSA 9":  "psa-9-price",
    "PSA 8":  "psa-8-price",
    "BGS 10": "bgs-10-price",
    "BGS 9.5":"bgs-9-5-price",
    "CGC 10": "cgc-10-price",
    "CGC 9.5":"cgc-9-5-price"
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

for card in holdings.get("poke", []):
    card_id   = card["id"]
    name      = card["name"]
    grade     = card["grade"]
    grade_key = GRADE_MAP.get(grade)

    try:
        # Search for card
        r = session.get(
            "https://www.pricecharting.com/api/products",
            params={"q": name, "type": "pokemon"},
            timeout=15
        )
        data = r.json()
        products = data.get("products", [])

        if not products:
            print(f"  {name[:40]}: not found")
            continue

        # Score match by word overlap
        name_lower = name.lower()
        best       = products[0]
        best_score = -1
        for prod in products[:10]:
            label = str(prod.get("product-name") or prod.get("name") or "").lower()
            score = sum(1 for w in name_lower.split() if len(w) > 2 and w in label)
            if score > best_score:
                best       = prod
                best_score = score

        # Fetch price data
        r2        = session.get(
            "https://www.pricecharting.com/api/product",
            params={"id": best["id"]},
            timeout=15
        )
        price_data = r2.json()

        raw = price_data.get(grade_key)
        if raw is not None:
            usd_price = raw / 100
            prices["poke"][card_id] = {"price": usd_price, "matched": best.get("product-name", name)}
            print(f"  [{grade}] {name[:40]}: ${usd_price:.2f}")
        else:
            print(f"  [{grade}] {name[:40]}: no price for this grade")

    except Exception as e:
        print(f"  {name[:40]}: error - {e}")

    time.sleep(1)  # Be polite to PriceCharting

# ── SAVE ──────────────────────────────────────────────────────────────
with open("prices.json", "w") as f:
    json.dump(prices, f, indent=2)

print(f"\nDone. Updated: {prices['updated']}")
