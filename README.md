# Gold Pulse: gold and silver price website

A gold and silver rate website with **49 pages**:

| Pages | How many | What's on them |
|---|---|---|
| Home (`index.html`) | 1 | Featured city gold + silver cards at the very top, all-city cards with search, hallmark tips, guides, tools |
| Gold rate per city (`gold-rate-<city>.html`) | 12 | 24K/22K/18K today, today's updates, price by weight, 7/30/90-day chart, last 10 days, calculator, questions |
| Silver home (`silver-rate-today.html`) | 1 | Featured city silver, all-city silver table |
| Silver rate per city (`silver-rate-<city>.html`) | 12 | Silver per gram and kg, today's updates, by weight up to 1 kg, 7/30/90-day chart, last 10 days, calculator |
| Guides hub + guides | 1 + 15 | Original articles (530–650 words each): rates, purity, hallmark, making charges, GST, selling, silver, care… |
| Tools | 2 | Gold weight converter (gram/pavan/tola/ounce), gold purity calculator |
| Site pages | 5 | About, Disclaimer, Privacy (with the AdSense cookie notice), Terms, Contact |

Every page also has a price strip under the header and a footer with links to cities, guides and tools.

**Look:** the "Swarna" pearl design (from `gold-rate-ui.zip`), **light only**: ivory background with champagne and
gold accents. Headings use Cinzel and text uses Plus Jakarta Sans. Both are free fonts stored in `static/fonts/`, so
nothing loads from Google. Taken from Swarna: weight chips (1 g, 8 g, 10 g, 1 tola, 100 g, 1 kg; gold pages start
at **10 g**, silver at **1 kg**), big price cards, the bill-style calculator with "Copy this estimate", the hallmark
section, and city cards with market names. Left out on purpose: dark mode, the fake "MCX/IBJA live" labels, the
currency switch, the refresh button and the price-alert pop-up.

**Page layout (desktop):**

| Screen width | Left column | Main content | Right column |
|---|---|---|---|
| 1440 px and wider | Quick links: today's prices, all cities, tools, popular guides (stays in view while scrolling) | Yes | Ad space, 300 × 600 (stays in view) |
| 1100–1439 px (laptops) | Hidden (its links are also in the top menu and footer) | Yes | Ad space |
| Under 1100 px (tablets, phones) | Hidden | Yes, full width | Hidden |

The top of each rate page is compact: the title and the weight chips sit side by side, and the price cards come
straight after. On a 1920 × 940 screen all four home-page cards are visible as soon as the page opens; on a
1366 × 768 laptop they fit too.

The ad space has a fixed size, so when an ad loads it can't push the prices or text around. While
`"ad_placeholders": true` in `config.json`, it shows a dashed "Ad space 300 × 600" box. Set it to `false` before
you apply for AdSense: the space stays reserved but shows nothing.

**Contact email** on every public page: `teraversestudio@gmail.com` (from `config.json` → `contact_email`).

It is plain HTML, CSS and a little JavaScript. There is no npm and there are no outside scripts or fonts,
and it has a strict security policy. A Python script (standard library only) builds the pages.

## Folder layout

| Path | What it is |
|---|---|
| `config.json` | Site name, web address, contact email, price feed, cities, tax and premium settings |
| `data/rates.json` | Every day's gold (`k24`,`k22`,`k18`) and silver (`s`, ₹/kg) price per city, newest first, up to 400 days, with that day's updates in `u` |
| `content/guides.json` | The list of guides: slug, topic, title, description |
| `content/guides/<slug>.html` | Each guide's text. Edit these to change or add guides |
| `tools/update_rates.py` | Adds new prices (from the internet or typed in by you) |
| `build.py` | Turns config + prices + guides into the finished pages in `site/` |
| `static/` | `style.css`, `app.js`, `fonts/` and the logo, copied to `site/assets/` |
| `site/` | **The finished website.** Upload this folder. It is rebuilt every time, so don't edit it by hand. |
| `.github/workflows/daily-rates.yml` | Runs 3 times a day on GitHub (10 AM, 2 PM, 6 PM IST): get prices → build → publish |
| `_headers`, `netlify.toml` | Security headers and build settings for Netlify |

## See it on your computer

```bash
cd "C:\Users\theam\Downloads\gold-rate-site"
```
```bash
python build.py
```
Then open `site\index.html` in your browser.

The site now shows **sample prices** with a yellow "Sample prices" note at the top.
To make new sample data, run `python tools/update_rates.py demo`.

## Getting real prices: pick one way

### A) Automatic, 3 times a day (in use now)

`config.json` → `"price_feed": "free"`. This needs **no key and no sign-up**:

| Source | Gives | Updated |
|---|---|---|
| api.gold-api.com | World gold and silver price (US$ per ounce) | Live |
| open.er-api.com | US$ → ₹ rate | Once a day |

Each run makes 3 small requests. There is no monthly limit. If a source is down, the run stops and the site keeps its last prices.
Free services can change without notice, so check now and then that "Updated …" on the site shows today's date.

Other feeds you can switch to in `config.json` (each needs a key in a GitHub secret):

| Feed | Key name | Note |
|---|---|---|
| `"metalpriceapi"` | `METALPRICEAPI_KEY` | Free plan is **daily only** (one price a day, up to a day old); paid plans are fresher |
| `"goldapi"` | `GOLDAPI_KEY` | 2 requests per run; free plan (100/month) is not enough for 3 runs a day |

**Calibrating (already done on 31 Oct 2026** against Chennai: 24K ₹13,888/g and silver ₹2,00,000/kg, giving
`premium_percent` 17.21 and `silver_premium_percent` 32.84). Redo it if the site's prices drift away from your local
rate, for example after an import-duty change in a Budget:
```bash
python tools/update_rates.py calibrate 13888
```
```bash
python tools/update_rates.py calibrate-silver 200000
```
(Use that day's local 24K rate per gram and silver rate per kg.) Then commit and push `config.json`.

### B) Type the rate yourself

```bash
python tools/update_rates.py set chennai 14226
```
```bash
python tools/update_rates.py set-silver chennai 210000
```
22K and 18K are worked out from 24K. To give all three yourself, or to fill in a past day:
```bash
python tools/update_rates.py set chennai 14226 13040 10667 --date 2026-10-30
```

The first real price you add deletes the sample data automatically. Only cities with prices get a page.

**Different cities:** with the automatic feed every city gets the same base price. If one city is usually a
few rupees different, put that gap in its `"offset"` (gold, ₹ per gram) or `"silver_offset"` (₹ per kg) in `config.json`.

## Put it online

### GitHub Pages (free, updates itself 3 times a day)

1. Make a new GitHub repository and upload everything in this folder **except `site/`**.
2. Repository → **Settings → Pages → Source: GitHub Actions**.
3. No secret is needed with the `"free"` feed. (Only for a keyed feed: Settings → Secrets and variables →
   Actions → New repository secret, named `METALPRICEAPI_KEY` or `GOLDAPI_KEY`.)
4. **Actions** tab → "Gold and silver rates" → **Run workflow**. From then on it runs at 10:00 AM, 2:00 PM and 6:00 PM India time.
   GitHub sometimes starts scheduled runs 5–30 minutes late. That is normal.
5. `config.json` → `site_url` is already set to `https://goldpulse.co.in` (used in the sitemap, robots.txt and page links for Google).

### Connect goldpulse.co.in (bought on GoDaddy)

**A. On GitHub:** Repository → **Settings → Pages → Custom domain** → type `goldpulse.co.in` → **Save**.
After the DNS step below works, tick **Enforce HTTPS** (this can take up to a day to become available).

**B. On GoDaddy:** **My Products → goldpulse.co.in → DNS** (Manage DNS). Delete any old `A` record for `@` or "Parked"
record, then add:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | @ | 185.199.108.153 | 1 hour |
| A | @ | 185.199.109.153 | 1 hour |
| A | @ | 185.199.110.153 | 1 hour |
| A | @ | 185.199.111.153 | 1 hour |
| CNAME | www | `<your-github-username>.github.io` | 1 hour |

These four numbers are GitHub Pages' own addresses. DNS changes usually work within an hour but can take up to 48 hours.

**C. Check it:** open `https://goldpulse.co.in`. Then, in **Google Search Console**, add a **Domain** property for
`goldpulse.co.in` (GoDaddy can verify it automatically), and submit the full address `https://goldpulse.co.in/sitemap.xml`.

### Netlify

Connect the GitHub repository. Netlify reads `netlify.toml`, runs `python build.py` and publishes `site/`.
Keep the GitHub workflow running so `data/rates.json` gets new prices. Netlify then rebuilds on every new commit.

## Getting ready for AdSense

AdSense has no fixed "number of pages" rule. Google looks for **useful, original content**, clear site pages
(About, Contact, Privacy) and easy navigation. The 15 guides and 2 tools are what carry the content here.
The 24 city pages share one layout, so they count for less on their own.

Before you apply:

- [x] `site_url` is `https://goldpulse.co.in` and the contact email is teraversestudio@gmail.com
- [ ] Connect the domain (steps above) and make sure `https://goldpulse.co.in` opens with the padlock
- [ ] Set `"ad_placeholders": false` in `config.json` so reviewers don't see empty dashed boxes
- [x] Real prices are on (free feed, since 31 Oct 2026); the sample note is gone
- [ ] Add your own name (or business name) and a line about yourself to the About page in `build.py` → `legal_pages()`
- [ ] Put the site on its own domain (for example a `.in` or `.com`) and submit `https://<your-site>/sitemap.xml` in Google Search Console
- [ ] Wait until Google has indexed most pages, then apply
- [ ] Keep adding a new guide every week or two (add a line to `content/guides.json` and a file in `content/guides/`)

When AdSense gives you the ad code:

1. Add `ads.txt` to the site root with the line AdSense gives you.
2. The security policy currently blocks outside scripts. Allow Google's ad domains by adding them to `script-src`,
   `img-src`, `frame-src` and `connect-src` in **both** `CSP` in `build.py` and `_headers`
   (AdSense's help pages list the domains).
3. Add the ad script tag to the `<head>` in `page()` in `build.py`, and put the ad unit code for the right
   column in `ad_rail()` in `build.py` (keep it 300 × 600 so nothing on the page moves). Then rebuild.

The privacy page already explains Google's advertising cookies.

## Notes

- **Changing the update times:** edit the `cron` line in `.github/workflows/daily-rates.yml` (the times are in UTC,
  which is India time minus 5:30), then change `update_times_ist` in `config.json` to match. The pages use it in their text.
- Prices are a guide. They don't include GST or making charges, and every page says so.
- Don't copy prices or text from other rate websites. Use your own feed or your own typed rates, and your own guides.
- To add a city, add a line to `cities` in `config.json` and rebuild.
