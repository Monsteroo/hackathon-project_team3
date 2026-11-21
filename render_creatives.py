#!/usr/bin/env python3
"""
Renders localized marketing creatives across all 3 formats (1080x1080, 1080x1920, 1200x628)
using Headless Google Chrome + HTML/CSS, and writes output/manifest.csv for A/B testing.
"""

import base64
import csv
import html
import json
import subprocess
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CAMPAIGN_PATH = BASE_DIR / "campaign.json"
SCENES_DIR = BASE_DIR / "assets" / "scenes"
OUTPUT_DIR = BASE_DIR / "output"

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def build_html(
    img_data_uri: str,
    brand: dict,
    copy: dict,
    width: int,
    height: int,
    theme: str,
) -> str:
    accent = brand.get("accent_color", "#C6F432")
    accent_text = brand.get("accent_text", "#111114")
    brand_name = html.escape(brand.get("name", "BRAND"))
    badge = html.escape(copy["badge"])
    headline = html.escape(copy["headline"])
    subheadline = html.escape(copy["subheadline"])
    cta = html.escape(copy["cta"])

    is_story = height > width
    is_banner = width > height

    fonts_link = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Onest:wght@600;700;800&subset=cyrillic,cyrillic-ext&display=swap" rel="stylesheet">'

    if is_banner:
        # 1200x628 landscape: clean left editorial panel + right product photo
        return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
{fonts_link}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: {width}px; height: {height}px; overflow: hidden;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #111114;
  }}
  .canvas {{
    position: relative; width: {width}px; height: {height}px;
    display: flex; align-items: stretch;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url("{img_data_uri}");
    background-size: cover; background-position: 75% center;
  }}
  .scrim {{
    position: absolute; inset: 0;
    background: linear-gradient(90deg, rgba(17,17,20,0.95) 0%, rgba(17,17,20,0.86) 48%, rgba(17,17,20,0.22) 76%, rgba(17,17,20,0.0) 100%);
  }}
  .content {{
    position: relative; z-index: 2;
    width: 62%; height: 100%;
    padding: 52px 56px;
    display: flex; flex-direction: column; justify-content: space-between;
    color: #FFFFFF;
  }}
  .top-row {{
    display: flex; align-items: center; gap: 14px;
  }}
  .brand {{
    font-family: 'Onest', sans-serif;
    font-size: 20px; font-weight: 800; letter-spacing: 0.14em; color: #FFFFFF;
    display: inline-flex; align-items: center; gap: 8px;
  }}
  .brand-dot {{
    width: 10px; height: 10px; border-radius: 999px; background: {accent}; display: inline-block;
  }}
  .badge {{
    display: inline-block; padding: 6px 14px; border-radius: 999px;
    background: rgba(198, 244, 50, 0.14); border: 1px solid rgba(198, 244, 50, 0.35);
    font-size: 13px; font-weight: 600; letter-spacing: 0.08em; color: #ECFCCB;
  }}
  .copy {{ display: flex; flex-direction: column; gap: 18px; }}
  h1 {{
    font-family: 'Onest', sans-serif;
    font-size: 50px; line-height: 1.08; font-weight: 700; letter-spacing: -0.02em;
    color: #FFFFFF;
  }}
  p {{
    font-size: 23px; line-height: 1.35; font-weight: 400; color: #E2E2E6;
    max-width: 92%;
  }}
  .cta {{
    align-self: flex-start;
    padding: 18px 34px; border-radius: 14px;
    background: {accent}; color: {accent_text};
    font-family: 'Onest', sans-serif;
    font-size: 22px; font-weight: 700; letter-spacing: -0.01em;
    box-shadow: 0 12px 30px rgba(17,17,20,0.45);
  }}
</style>
</head>
<body>
  <div class="canvas">
    <div class="bg"></div>
    <div class="scrim"></div>
    <div class="content">
      <div class="top-row">
        <span class="brand"><span class="brand-dot"></span>{brand_name}</span>
        <span class="badge">{badge}</span>
      </div>
      <div class="copy">
        <h1>{headline}</h1>
        <p>{subheadline}</p>
      </div>
      <div class="cta">{cta} →</div>
    </div>
  </div>
</body>
</html>"""

    # Square (1080x1080) or Story (1080x1920)
    pad_top = 150 if is_story else 64
    pad_bottom = 180 if is_story else 64
    pad_x = 76 if is_story else 68
    h1_size = 76 if is_story else 62
    p_size = 34 if is_story else 28
    cta_size = 32 if is_story else 26
    cta_pad = "26px 52px" if is_story else "20px 40px"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
{fonts_link}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: {width}px; height: {height}px; overflow: hidden;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #111114;
  }}
  .canvas {{
    position: relative; width: {width}px; height: {height}px;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: {pad_top}px {pad_x}px {pad_bottom}px {pad_x}px;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url("{img_data_uri}");
    background-size: cover; background-position: center 62%;
  }}
  .scrim-top {{
    position: absolute; top: 0; left: 0; right: 0; height: 56%;
    background: linear-gradient(180deg, rgba(17,17,20,0.92) 0%, rgba(17,17,20,0.68) 55%, rgba(17,17,20,0.0) 100%);
  }}
  .scrim-bottom {{
    position: absolute; bottom: 0; left: 0; right: 0; height: 34%;
    background: linear-gradient(0deg, rgba(17,17,20,0.88) 0%, rgba(17,17,20,0.38) 55%, rgba(17,17,20,0.0) 100%);
  }}
  .header {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; gap: 22px; color: #FFFFFF;
  }}
  .top-row {{
    display: flex; align-items: center; justify-content: space-between;
  }}
  .brand {{
    font-family: 'Onest', sans-serif;
    font-size: 24px; font-weight: 800; letter-spacing: 0.14em; color: #FFFFFF;
    display: inline-flex; align-items: center; gap: 10px;
  }}
  .brand-dot {{
    width: 12px; height: 12px; border-radius: 999px; background: {accent}; display: inline-block;
  }}
  .badge {{
    display: inline-block; padding: 8px 18px; border-radius: 999px;
    background: rgba(198, 244, 50, 0.14); border: 1px solid rgba(198, 244, 50, 0.35);
    font-size: 16px; font-weight: 600; letter-spacing: 0.08em; color: #ECFCCB;
    backdrop-filter: blur(8px);
  }}
  h1 {{
    font-family: 'Onest', sans-serif;
    font-size: {h1_size}px; line-height: 1.07; font-weight: 700; letter-spacing: -0.025em;
    color: #FFFFFF; text-shadow: 0 4px 20px rgba(17,17,20,0.45);
  }}
  p {{
    font-size: {p_size}px; line-height: 1.32; font-weight: 400; color: #E2E2E6;
    max-width: 94%;
  }}
  .footer {{
    position: relative; z-index: 2;
    display: flex; align-items: center; justify-content: flex-start;
  }}
  .cta {{
    padding: {cta_pad}; border-radius: 14px;
    background: {accent}; color: {accent_text};
    font-family: 'Onest', sans-serif;
    font-size: {cta_size}px; font-weight: 700; letter-spacing: -0.01em;
    box-shadow: 0 14px 36px rgba(17,17,20,0.45);
  }}
</style>
</head>
<body>
  <div class="canvas">
    <div class="bg"></div>
    <div class="scrim-top"></div>
    <div class="scrim-bottom"></div>
    <div class="header">
      <div class="top-row">
        <span class="brand"><span class="brand-dot"></span>{brand_name}</span>
        <span class="badge">{badge}</span>
      </div>
      <h1>{headline}</h1>
      <p>{subheadline}</p>
    </div>
    <div class="footer">
      <div class="cta">{cta} →</div>
    </div>
  </div>
</body>
</html>"""


def render_png(html_content: str, width: int, height: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp:
        tmp.write(html_content)
        tmp_path = Path(tmp.name)
    try:
        cmd = [
            CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            f"--screenshot={out_path}",
            tmp_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> None:
    campaign = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    brand = campaign["brand"]
    formats = campaign["formats"]
    locales = campaign["locales"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    total = 0

    for scene in campaign["scenes"]:
        scene_path = SCENES_DIR / f"{scene['id']}.png"
        if not scene_path.exists():
            raise FileNotFoundError(f"Missing scene image: {scene_path}")
        b64 = base64.b64encode(scene_path.read_bytes()).decode("ascii")
        img_uri = f"data:image/png;base64,{b64}"

        for locale in locales:
            copy = scene["copy"][locale]
            for fmt in formats:
                creative_id = f"{scene['id']}_{locale}_{fmt['id']}"
                out_path = OUTPUT_DIR / locale / fmt["id"] / f"{creative_id}.png"
                html_doc = build_html(
                    img_uri, brand, copy, fmt["width"], fmt["height"], scene.get("theme", "dark_overlay")
                )
                render_png(html_doc, fmt["width"], fmt["height"], out_path)
                total += 1
                manifest_rows.append(
                    {
                        "creative_id": creative_id,
                        "scene_id": scene["id"],
                        "hypothesis": scene["hypothesis"],
                        "locale": locale,
                        "format": fmt["id"],
                        "width": fmt["width"],
                        "height": fmt["height"],
                        "headline": copy["headline"],
                        "subheadline": copy["subheadline"],
                        "cta": copy["cta"],
                        "file_path": str(out_path.relative_to(BASE_DIR)),
                    }
                )
                print(f"[Render] ({total}) {out_path.relative_to(BASE_DIR)}", flush=True)

    manifest_path = OUTPUT_DIR / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\nDone! Rendered {total} creatives + {manifest_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
