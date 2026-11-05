"""Builds index.html for ELBRAD Variante B.

The weather logic in src/shared/weather.js is inlined into the page script.
It is the same file as in the elbrad-variante-a repository, so both versions
fetch, validate and format the weather identically. If you change it, change
it in both repositories.

Images are not touched here: they live directly in assets/img/ so they can be
replaced by uploading files with the same names.

Usage: python3 build.py
"""
import pathlib
import shutil

root = pathlib.Path(__file__).parent
IMAGES = ["citybike.jpg", "ebike.jpg", "tourenrad.jpg", "saddle.jpg", "handlebar.jpg", "waterfront.jpg"]

html = (root / "src/template.html").read_text(encoding="utf-8")
html = html.replace("{{WEATHER_JS}}", (root / "src/shared/weather.js").read_text(encoding="utf-8"))
assert "{{" not in html, "unreplaced placeholder"

fonts = root / "assets/fonts"
fonts.mkdir(parents=True, exist_ok=True)
for f in sorted((root / "src/fonts").glob("*.woff2")):
    shutil.copy2(f, fonts / f.name)

(root / "index.html").write_text(html, encoding="utf-8")
missing = [n for n in IMAGES if not (root / "assets/img" / n).exists()]
print("index.html", len(html) // 1024, "KB" + ("  | missing images: " + ", ".join(missing) if missing else ""))
