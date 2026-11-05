"""Headless Chrome checks for index.html (ELBRAD Variante B).

Mocked API responses are used ONLY here, through request interception, to cover
edge cases. The page itself has no mock or fallback data.
Run: python3 tests/test_page.py
"""
import json, time, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = (ROOT / "index.html").as_uri()
OUT = ROOT / "tests/output"; OUT.mkdir(parents=True, exist_ok=True)
API = "https://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m,wind_speed_10m&hourly=precipitation_probability&forecast_days=1&timezone=Europe%2FBerlin"
CHROME = "/usr/bin/google-chrome"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""))


def payload(temp=10.3, wind=12.4, probs=None, cur_time="2026-11-05T15:45", day="2026-11-05", drop=()):
    probs = probs if probs is not None else [i * 3 + 1 for i in range(24)]  # index 15 -> 46
    d = {"latitude": 53.54, "longitude": 10.0, "utc_offset_seconds": 3600, "timezone": "Europe/Berlin",
         "current_units": {"time": "iso8601", "interval": "seconds", "temperature_2m": "°C", "wind_speed_10m": "km/h"},
         "current": {"time": cur_time, "interval": 900, "temperature_2m": temp, "wind_speed_10m": wind},
         "hourly_units": {"time": "iso8601", "precipitation_probability": "%"},
         "hourly": {"time": [f"{day}T{h:02d}:00" for h in range(24)], "precipitation_probability": probs}}
    for path in drop:
        obj = d
        *parents, last = path.split(".")
        for p in parents: obj = obj[p]
        obj.pop(last, None)
    return d


def norm(s): return s.replace(" ", " ")


def weather(page):
    return page.evaluate("""() => { const g = id => document.getElementById(id);
      return { status: g('weather-status').textContent, statusVisible: !g('weather-status').classList.contains('sr-only'),
        errorShown: !g('weather-error').hidden, statsShown: !g('weather-stats').hidden,
        temp: g('w-temp').textContent, precip: g('w-precip').textContent, hour: g('w-precip-hour').textContent,
        wind: g('w-wind').textContent, time: g('w-time').textContent }; }""")


def json_route(data, status=200):
    def h(route):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data),
                      headers={"Access-Control-Allow-Origin": "*"})
    return h


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])

    def new_page(width=1440, height=900, route=None, reduced=False, tz="Europe/Berlin"):
        ctx = browser.new_context(viewport={"width": width, "height": height}, locale="de-DE", timezone_id=tz,
                                  reduced_motion="reduce" if reduced else "no-preference")
        page = ctx.new_page()
        page.errors, page.api = [], []
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("request", lambda r: page.api.append(r.url) if "open-meteo" in r.url else None)
        if route: page.route("**/api.open-meteo.com/**", route)
        return page

    def loaded(p): p.wait_for_function("!document.getElementById('weather-stats').hidden", timeout=8000)
    def failed(p, t=15000): p.wait_for_function("!document.getElementById('weather-error').hidden", timeout=t)

    # --- Real request without interception: this sandbox blocks open-meteo -> genuine network failure
    p = new_page(); p.goto(PAGE); failed(p)
    w = weather(p)
    check("real network failure -> error message", w["status"] == "Wetterdaten gerade nicht erreichbar." and w["errorShown"], w["status"])
    check("request uses the exact endpoint", p.api[:1] == [API], p.api[:1])
    check("no values shown after failure", not w["statsShown"] and w["time"] == "Nicht verfügbar")
    p.context.close()

    # --- Loading state: hold the request open
    held = []
    p = new_page(route=lambda r: held.append(r)); p.goto(PAGE)
    p.wait_for_function("document.querySelector('.weather-body').getAttribute('aria-busy') === 'true'", timeout=3000)
    w = weather(p)
    check("loading message while pending", w["status"] == "Wetterdaten werden geladen …" and w["statusVisible"] and not w["statsShown"], w["status"])
    check("status region is role=status, aria-live=polite", p.evaluate("[document.getElementById('weather-status').role || document.getElementById('weather-status').getAttribute('role'), document.getElementById('weather-status').getAttribute('aria-live')]") == ["status", "polite"])
    held[0].fulfill(status=200, content_type="application/json", body=json.dumps(payload()), headers={"Access-Control-Allow-Origin": "*"})
    loaded(p)
    check("loading -> data after response", norm(weather(p)["temp"]) == "10,3 °C")
    p.context.close()

    # --- Field mapping
    p = new_page(route=json_route(payload())); p.goto(PAGE); loaded(p)
    w = weather(p)
    check("temperature from current.temperature_2m", norm(w["temp"]) == "10,3 °C", w["temp"])
    check("wind from current.wind_speed_10m", norm(w["wind"]) == "12,4 km/h", w["wind"])
    check("precip from matching hour (index 15, not 0)", norm(w["precip"]) == "46 %", w["precip"])
    check("forecast hour shown", norm(w["hour"]) == "Stundenwert 15:00 Uhr", w["hour"])
    check("timestamp from current.time", norm(w["time"]) == "05.11.2026, 15:45 Uhr", w["time"])
    check("result announced in status region", w["status"].startswith("Wetterdaten geladen.") and not w["statusVisible"], norm(w["status"]))
    check("no console errors", not p.errors, p.errors)
    p.context.close()

    for tz in ("America/New_York", "Asia/Tokyo"):
        p = new_page(route=json_route(payload()), tz=tz); p.goto(PAGE); loaded(p)
        w = weather(p)
        check(f"no timezone shift for visitor in {tz}", norm(w["time"]) == "05.11.2026, 15:45 Uhr" and norm(w["hour"]) == "Stundenwert 15:00 Uhr", f'{w["time"]} / {w["hour"]}')
        p.context.close()

    # --- Zero values
    probs = [80] + [5] * 23; probs[9] = 0
    p = new_page(route=json_route(payload(temp=0, wind=0, probs=probs, cur_time="2026-11-05T09:30"))); p.goto(PAGE); loaded(p)
    w = weather(p)
    check("0 % precipitation displayed (first entry is 80)", norm(w["precip"]) == "0 %" and norm(w["hour"]) == "Stundenwert 09:00 Uhr", f'{w["precip"]} / {w["hour"]}')
    check("0 °C and 0 km/h displayed", norm(w["temp"]) == "0,0 °C" and norm(w["wind"]) == "0,0 km/h", f'{w["temp"]} / {w["wind"]}')
    p.context.close()

    # --- Missing / invalid fields, validated individually
    probs = [10] * 24; probs[15] = None
    p = new_page(route=json_route(payload(wind="12", probs=probs, drop=("current.temperature_2m",)))); p.goto(PAGE); loaded(p)
    w = weather(p)
    check("missing temperature -> Nicht verfügbar", w["temp"] == "Nicht verfügbar", w["temp"])
    check("non-numeric wind -> Nicht verfügbar", w["wind"] == "Nicht verfügbar", w["wind"])
    check("null precipitation -> Nicht verfügbar", w["precip"] == "Nicht verfügbar", w["precip"])
    check("valid timestamp still shown", norm(w["time"]) == "05.11.2026, 15:45 Uhr", w["time"])
    p.context.close()
    p = new_page(route=json_route(payload(day="2026-11-04"))); p.goto(PAGE); loaded(p)
    check("no matching hour -> Nicht verfügbar", weather(p)["precip"] == "Nicht verfügbar")
    p.context.close()

    # --- HTTP error, retry, invalid JSON, timeout
    state = {"fail": True}
    def flaky(route):
        if state["fail"]: route.fulfill(status=500, body="error", headers={"Access-Control-Allow-Origin": "*"})
        else: json_route(payload())(route)
    p = new_page(route=flaky); p.goto(PAGE); failed(p)
    check("HTTP 500 -> error message", weather(p)["status"] == "Wetterdaten gerade nicht erreichbar.")
    state["fail"] = False
    p.get_by_role("button", name="Erneut versuchen").click(); loaded(p)
    check("Erneut versuchen loads data", norm(weather(p)["temp"]) == "10,3 °C" and len(p.api) == 2)
    p.context.close()
    p = new_page(route=lambda r: r.fulfill(status=200, content_type="application/json", body="<html>", headers={"Access-Control-Allow-Origin": "*"}))
    p.goto(PAGE); failed(p); check("invalid JSON -> error message", True); p.context.close()
    p = new_page(route=lambda r: None)
    t0 = time.time(); p.goto(PAGE); failed(p, 20000); el = time.time() - t0
    check("timeout -> error after about 10 s", 9 <= el <= 14, f"{el:.1f}s")
    p.screenshot(path=str(OUT / "b-error.png"))
    p.context.close()

    # --- Navigation, dialog, preselection, focus
    p = new_page(route=json_route(payload())); p.goto(PAGE); loaded(p); p.wait_for_timeout(200)
    for label, target in [("Räder", "raeder"), ("So geht’s", "ablauf"), ("Preise", "preise")]:
        p.evaluate("scrollTo(0,0)"); p.wait_for_timeout(100)
        p.get_by_role("navigation").get_by_role("link", name=label, exact=True).click(); p.wait_for_timeout(1200)
        top = p.evaluate(f"document.getElementById('{target}').getBoundingClientRect().top")
        bottom = p.evaluate("Math.ceil(scrollY + innerHeight) >= document.documentElement.scrollHeight")
        check(f"nav '{label}' -> #{target}", abs(top) < 30 or (bottom and top > 0), f"top={top:.0f}")

    triggers = p.evaluate("[...document.querySelectorAll('[data-open-booking]')].map(b => b.textContent.trim().replace(/\\s+/g,' '))")
    check("six booking buttons", len(triggers) == 6, triggers)
    for i in range(6):
        p.evaluate("document.querySelectorAll('#booking input').forEach(r => r.checked = false)")
        btn = p.locator("[data-open-booking]").nth(i)
        btn.scroll_into_view_if_needed(); btn.focus(); p.keyboard.press("Enter"); p.wait_for_timeout(150)
        bike = btn.get_attribute("data-bike")
        st = p.evaluate("""() => ({ open: document.getElementById('booking').open,
            checked: (document.querySelector('#booking input:checked') || {}).value || null,
            focus: document.activeElement.id })""")
        expect = bike if bike else None
        check(f"button {i + 1} ({triggers[i]}) opens dialog, preselect={expect}", st["open"] and st["checked"] == expect,
              st)
        p.keyboard.press("Escape"); p.wait_for_timeout(150)
        restored = p.evaluate("(el => el === document.activeElement)", btn.element_handle())
        check(f"button {i + 1}: Escape closes, focus restored", not p.evaluate("document.getElementById('booking').open") and restored)

    # dialog content and keyboard
    p.locator("[data-bike=\"E-Bike\"]").click(); p.wait_for_timeout(150)
    check("Rad wählen buttons have distinct names", p.get_by_role("button", name="E-Bike").count() == 1 and p.get_by_role("button", name="Tourenrad").count() == 1)
    check("dialog accessible name", p.get_by_role("dialog", name="Rad buchen").count() == 1)
    check("notice text exact", p.text_content("#booking-note") == "Dies ist ein Studienprojekt. Es wird keine echte Buchung vorgenommen.")
    check("no personal/payment fields", p.evaluate("document.querySelectorAll('#booking input:not([type=radio]), #booking select, #booking textarea').length") == 0)
    check("selector lists three bikes with prices", [norm(x) for x in p.evaluate("[...document.querySelectorAll('#booking .choice')].map(l => l.textContent.trim())")] ==
          ["Citybike12 € / Tag", "E-Bike25 € / Tag", "Tourenrad18 € / Tag"])
    p.keyboard.press("ArrowDown"); p.wait_for_timeout(100)
    check("arrow key changes selection", p.evaluate("document.querySelector('#booking input:checked').value") == "Tourenrad")
    check("selection summary updates", "Tourenrad" in p.text_content("#booking-selected"), norm(p.text_content("#booking-selected")))
    inside = True
    for _ in range(12):
        p.keyboard.press("Tab")
        inside = inside and p.evaluate("document.getElementById('booking').contains(document.activeElement)")
    for _ in range(12):
        p.keyboard.press("Shift+Tab")
        inside = inside and p.evaluate("document.getElementById('booking').contains(document.activeElement)")
    check("Tab / Shift+Tab stay inside the dialog", inside)
    p.screenshot(path=str(OUT / "b-dialog-desktop.png"))
    p.get_by_role("button", name="Dialog schließen").click()
    check("close (X) button closes", not p.evaluate("document.getElementById('booking').open"))
    p.get_by_role("button", name="Rad buchen", exact=True).click(); p.wait_for_timeout(100)
    p.get_by_role("button", name="Schließen", exact=True).click()
    check("Schließen button closes", not p.evaluate("document.getElementById('booking').open"))
    p.get_by_role("button", name="Rad buchen", exact=True).click(); p.wait_for_timeout(100)
    p.mouse.click(5, 5)
    check("backdrop click closes", not p.evaluate("document.getElementById('booking').open"))

    # focus visibility and basics
    p.goto(PAGE); p.wait_for_timeout(300); p.keyboard.press("Tab")
    check("skip link first", p.evaluate("document.activeElement.className") == "skip-link")
    p.keyboard.press("Tab"); p.keyboard.press("Tab")
    oc = p.evaluate("getComputedStyle(document.activeElement).outlineStyle + ' ' + getComputedStyle(document.activeElement).outlineWidth")
    check("visible focus outline", oc == "solid 3px", oc)
    check("robots meta", p.evaluate("document.querySelector('meta[name=robots]').content") == "noindex, nofollow")
    check("footer text exact", p.evaluate("document.querySelector('footer p').textContent") == "Studienprojekt der Kunstschule Wandsbek, keine offizielle Seite")
    links = p.evaluate("[...document.querySelectorAll('.weather-meta a')].map(a => [a.textContent.trim(), a.href])")
    check("attribution links", links == [["Wetterdaten: Open-Meteo", "https://open-meteo.com/"], ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"]], links)
    check("no 'Beispieldaten' on page", "Beispieldaten" not in p.evaluate("document.body.innerText"))
    p.context.close()

    # --- Responsive
    for wdt in (320, 375, 390, 768, 1024, 1440, 1920):
        p = new_page(width=wdt, route=json_route(payload())); p.goto(PAGE); loaded(p)
        p.evaluate("document.querySelectorAll('img').forEach(i => i.loading = 'eager')")
        p.wait_for_function("[...document.images].every(i => i.complete)", timeout=10000); p.wait_for_timeout(200)
        sw = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check(f"{wdt}px: no horizontal overflow", sw[0] <= sw[1], sw)
        small = p.evaluate("""() => [...document.querySelectorAll('p,a,button,h1,h2,h3,span,label,legend,li')]
            .filter(e => e.offsetParent && e.textContent.trim() && !e.closest('.sr-only'))
            .filter(e => parseFloat(getComputedStyle(e).fontSize) < 14).map(e => e.textContent.trim().slice(0,30))""")
        check(f"{wdt}px: no text under 14px", not small, small[:3])
        fits = p.evaluate("""() => [...document.querySelectorAll('.hero-figure img, .bike-photo img, .tile--bike img')]
            .every(i => getComputedStyle(i).objectFit === 'contain')""")
        check(f"{wdt}px: bicycle photos are not cropped (object-fit: contain)", fits)
        targets = p.evaluate("""() => [...document.querySelectorAll('a[href^="#"]:not(.skip-link), button')].filter(e => e.offsetParent)
            .map(e => e.getBoundingClientRect()).filter(r => r.height < 44).length""")
        check(f"{wdt}px: touch targets at least 44px high", targets == 0, targets)
        if wdt in (390, 1440):
            p.screenshot(path=str(OUT / f"b-full-{wdt}.png"), full_page=True)
        p.context.close()

    p = new_page(route=json_route(payload())); p.goto(PAGE)
    imgs = p.evaluate("Promise.all([...document.images].map(i => i.decode().then(() => [i.alt.length, i.naturalWidth]).catch(() => [i.alt.length, 0])))")
    check("all images load and have alt text", all(a > 20 and nw > 0 for a, nw in imgs), imgs)
    fonts = p.evaluate("document.fonts.ready.then(() => [...document.fonts].filter(f => f.status === 'loaded').length)")
    check("self-hosted fonts load", fonts >= 3, fonts)
    p.context.close()
    p = new_page(route=json_route(payload()), reduced=True); p.goto(PAGE)
    check("reduced motion disables smooth scrolling", p.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto")
    p.context.close()
    browser.close()

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
