# ELBRAD · Variante B (Industrial)

Landing page for **ELBRAD**, a fictional bicycle rental service in Hamburg. Version B of the design assignment; Version A lives in [elbrad-variante-a](https://github.com/JakaSowaka/elbrad-variante-a) (where this version is also kept under `version-b/`).
Studienprojekt der Kunstschule Wandsbek, keine offizielle Seite.

Open `index.html` in a browser, or use the GitHub Pages address `https://jakasowaka.github.io/elbrad-variante-b/` once Pages is turned on (Settings → Pages → Deploy from a branch → `main`, `/ (root)`).

## Live weather

The "Hamburg heute" strip loads current data from [Open-Meteo](https://open-meteo.com/) on every page load, in `loadWeather()` (source: `src/shared/weather.js`, the same file as in Version A):

```
https://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m,wind_speed_10m&hourly=precipitation_probability&forecast_days=1&timezone=Europe%2FBerlin
```

- Temperature from `current.temperature_2m`, wind from `current.wind_speed_10m`, timestamp from `current.time`, read as Berlin time without converting to the visitor's timezone.
- Precipitation probability from the `hourly.time` entry with the same date and hour as `current.time`, at the same index.
- Loading and error messages, "Erneut versuchen", a 10-second timeout and "Nicht verfügbar" for each missing or invalid field. No sample or fallback values.

Weather data: Open-Meteo, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Adding the images

Upload six JPEG files with exactly these names to `assets/img/` (on GitHub: open the folder, **Add file → Upload files**, commit). Files with the same name replace the "Bild folgt" placeholders. No build step is needed.

| File | Subject | Ratio |
| --- | --- | --- |
| `citybike.jpg` | city bike with basket, side view, light grey studio floor (used in hero, Citybike card and mosaic) | 3:2, e.g. 1600 × 1067 |
| `ebike.jpg` | e-bike, same style | 3:2 |
| `tourenrad.jpg` | touring bike, same style | 3:2 |
| `saddle.jpg` | saddle close-up | 4:3, e.g. 1200 × 900 |
| `handlebar.jpg` | handlebar close-up | 4:3 |
| `waterfront.jpg` | cyclist by the Hamburg waterfront | 4:3 |

Then record source and rights in `docs/BILDQUELLEN.md`, and check that the image descriptions (`alt` texts in `src/template.html`, then rebuild, or directly in `index.html`) match your pictures.

## Files

| Path | Contents |
| --- | --- |
| `index.html` | Built page (generated from `src/template.html`) |
| `assets/` | Images and fonts used by the page |
| `src/template.html` | Source: HTML, CSS and page script |
| `src/shared/weather.js` | Weather logic, identical to Version A |
| `src/fonts/` | Plus Jakarta Sans (SIL Open Font License 1.1) |
| `build.py` | Builds `index.html` |
| `tests/test_page.py` | 90 headless Chrome checks (Playwright) |
| `docs/BILDQUELLEN.md` | Image sources and licences |

## Rebuild and test

```
python3 build.py
pip install playwright
python3 tests/test_page.py
```

The tests use intercepted, mocked API responses only to cover edge cases (zero values, missing fields, HTTP errors, timeout). The page itself never uses mock data.
