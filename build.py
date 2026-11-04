#!/usr/bin/env python3
"""Builds the website into docs/ from the stories in content/.

    python3 -I build.py                    build everything
    python3 -I build.py --content DIR --out DIR   build from other folders (for testing)

No installs needed: it uses Python and macOS's own image tools (sips and ImageIO).
Photos are resized for phones, tablets and big screens, turned the right way up, and
stripped of hidden metadata, so a photo never reveals its GPS location.
"""
import argparse, base64, html, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIDTHS = (800, 1600, 2400)
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"}
FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900"
         "&family=Courier+Prime:wght@400;700"
         "&family=Newsreader:ital,opsz,wght@0,6..72,300..600;1,6..72,300..500&display=swap")


def esc(text):
    return html.escape(str(text), quote=True)


def inline(text):
    """Escapes a line of text and turns *this* into italics."""
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc(text))


def parse_story(path):
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not match:
        sys.exit(f"{path} needs a --- header at the top")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    for key in ("title", "dek", "place", "country", "lat", "lon", "tz"):
        if key not in meta:
            sys.exit(f"{path} is missing '{key}' in its header")
    meta["lat"], meta["lon"] = float(meta["lat"]), float(meta["lon"])
    meta["blocks"] = parse_blocks(match.group(2))
    meta["slug"] = re.sub(r"^\d+-", "", path.parent.name)
    meta["folder"] = path.parent
    words = " ".join(b["text"] for b in meta["blocks"] if b["kind"] == "p").split()
    meta["words"] = len(words)
    meta["minutes"] = max(1, round(len(words) / 200))
    return meta


PHOTO_LINE = re.compile(r"!\[(.*?)\]\((.+?)\)")


def parse_blocks(body):
    blocks = []
    for chunk in re.split(r"\n\s*\n", body.strip()):
        chunk = chunk.strip()
        lines = chunk.splitlines()
        if chunk == "***":
            blocks.append({"kind": "break"})
        elif all(PHOTO_LINE.fullmatch(l.strip()) for l in lines):
            photos = [PHOTO_LINE.fullmatch(l.strip()).groups() for l in lines]
            blocks.append({"kind": "photos", "photos": [{"caption": c, "file": f} for c, f in photos]})
        elif chunk.startswith("> "):
            blocks.append({"kind": "pull", "text": " ".join(l.lstrip("> ") for l in lines)})
        elif lines[0].startswith(":::"):
            items = [l[2:] for l in lines[1:] if l.startswith("- ")]
            blocks.append({"kind": "notes", "title": lines[0][3:].strip() or "Field notes", "items": items})
        else:
            blocks.append({"kind": "p", "text": " ".join(lines)})
    return blocks


def sips_size(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                         capture_output=True, text=True, check=True).stdout
    found = dict(re.findall(r"(pixelWidth|pixelHeight): (\d+)", out))
    return int(found["pixelWidth"]), int(found["pixelHeight"])


def strip_metadata(path):
    """Removes EXIF, GPS, XMP and comments from a JPEG, and keeps the colour profile."""
    data = path.read_bytes()
    out, i = bytearray(data[:2]), 2
    while i < len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:
            out += data[i:]
            break
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if marker not in (0xE1, 0xED, 0xFE):
            out += data[i:i + 2 + length]
        i += 2 + length
    path.write_bytes(bytes(out))


def run_sips(*args):
    subprocess.run(["sips", *map(str, args)], capture_output=True, check=True)


def process_photo(source, folder):
    """Makes sized copies and returns what the page needs to show the photo well."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9]+", "-", source.stem.lower()).strip("-")
    info = folder / f"{stem}.json"
    if info.exists() and info.stat().st_mtime > source.stat().st_mtime:
        return json.loads(info.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        upright = Path(tmp) / "upright.jpg"
        subprocess.run(["swift", str(ROOT / "tools" / "upright.swift"), str(source), str(upright)],
                       capture_output=True, check=True)
        w, h = sips_size(upright)
        sizes = []
        for final in [x for x in WIDTHS if x < w] + [min(w, WIDTHS[-1])]:
            out = folder / f"{stem}-{final}.jpg"
            run_sips("-s", "format", "jpeg", "-s", "formatOptions", 82, "--resampleWidth", final, upright, "--out", out)
            strip_metadata(out)
            sizes.append((final, out.name))
        tiny = Path(tmp) / "tiny.jpg"
        run_sips("-s", "format", "jpeg", "-s", "formatOptions", 40, "-Z", 24, upright, "--out", tiny)
        strip_metadata(tiny)
        blur = "data:image/jpeg;base64," + base64.b64encode(tiny.read_bytes()).decode()
    result = {"w": w, "h": h, "sizes": sizes, "blur": blur}
    info.write_text(json.dumps(result))
    return result


def placeholder_ratio(name):
    match = re.fullmatch(r"placeholder-(\d+)x(\d+)", name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def picture(photo, story, out, prefix, sizes, eager=False):
    """Returns the <figure> for one photo, either real or a marked empty frame."""
    ratio = placeholder_ratio(photo["file"])
    caption = inline(photo["caption"])
    if ratio:
        photo["aspect"] = ratio[0] / ratio[1]
        return (f'<figure><div class="placeholder" style="aspect-ratio:{ratio[0]}/{ratio[1]}">Your photo goes here</div>'
                f"<figcaption>{caption}</figcaption></figure>")
    source = story["folder"] / photo["file"]
    if not source.exists():
        sys.exit(f"Photo not found: {source}")
    if source.suffix.lower() not in PHOTO_TYPES:
        sys.exit(f"Not a photo type I can use: {source}")
    data = process_photo(source, out / "photos" / story["slug"])
    photo["aspect"] = data["w"] / data["h"]
    base = f'{prefix}photos/{story["slug"]}/'
    srcset = ", ".join(f"{base}{name} {w}w" for w, name in data["sizes"])
    largest = base + data["sizes"][-1][1]
    medium = base + data["sizes"][min(1, len(data["sizes"]) - 1)][1]
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<figure><a class="photo-link" href="{esc(largest)}" data-caption="{esc(photo["caption"])}">'
            f'<span class="frame" style="background-image:url({data["blur"]})">'
            f'<img src="{esc(medium)}" srcset="{esc(srcset)}" sizes="{sizes}" width="{data["w"]}" height="{data["h"]}" '
            f'alt="{esc(photo["caption"])}" {loading} decoding="async"></span></a>'
            f"<figcaption>{caption}</figcaption></figure>")


def photo_group(photos, story, out, prefix):
    """One landscape runs wide, one portrait stays modest, and several share a row
    at their true proportions, so nothing gets cropped."""
    if len(photos) == 1:
        figure = picture(photos[0], story, out, prefix, "(max-width: 1200px) 100vw, 1128px")
        layout = "wide" if photos[0]["aspect"] >= 1 else "tall"
        return f'<div class="photos {layout}">{figure}</div>'
    figures = [picture(p, story, out, prefix, f"(max-width: 560px) 100vw, {round(100 / len(photos))}vw") for p in photos]
    cells = "".join(f.replace("<figure>", f'<figure style="flex:{p["aspect"]:.3f} 1 0">', 1) for f, p in zip(figures, photos))
    return f'<div class="photos wide"><div class="row">{cells}</div></div>'


def render_block(block, story, out, prefix):
    kind = block["kind"]
    if kind == "p":
        return f'<p>{inline(block["text"])}</p>'
    if kind == "break":
        return '<div class="break" aria-hidden="true">* * *</div>'
    if kind == "pull":
        return f'<blockquote class="pull">{inline(block["text"])}</blockquote>'
    if kind == "notes":
        items = "".join(f"<li>{inline(i)}</li>" for i in block["items"])
        return f'<aside class="notes"><h2>{esc(block["title"])}</h2><ul>{items}</ul></aside>'
    return photo_group(block["photos"], story, out, prefix)


def page(title, description, prefix, body, data, scripts):
    tags = "".join(f'<script src="{prefix}assets/{name}"></script>' for name in scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#ffffff">
<script>try{{if(localStorage.getItem('theme')==='dark')document.documentElement.setAttribute('data-theme','dark')}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to the stories</a>
{body}
<script>window.SITE={json.dumps(data, ensure_ascii=False).replace("</", "<\\/")};</script>
{tags}
</body>
</html>
"""


def masthead(config, prefix):
    return f"""<header class="top wrap">
<a class="brand" href="{prefix}index.html">{esc(config["name"])}</a>
<nav aria-label="Main menu">
<a href="{prefix}index.html#all">The map</a>
<a href="{prefix}index.html#about">About</a>
<button type="button" class="link-button" id="text-size" aria-pressed="false">Larger text</button>
<button type="button" class="link-button" id="theme">Dark mode</button>
</nav>
</header>"""


def stats(stories, upcoming):
    countries = len({s["country"] for s in stories})
    places = len({s["place"] for s in stories})
    minutes = sum(s["minutes"] for s in stories)
    plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else ("" if word.endswith("s") else "s"))
    country_word = "country" if countries == 1 else "countries"
    return f'{plural(len(stories), "story").replace("storys", "stories")}, {countries} {country_word}, {plural(places, "place")}, {minutes} minutes of reading'


def build_home(config, stories, out):
    rows = []
    for i, s in enumerate(stories):
        thumb = ""
        cover = s.get("cover") or next((p["file"] for b in s["blocks"] if b["kind"] == "photos"
                                        for p in b["photos"] if not placeholder_ratio(p["file"])), None)
        if cover:
            data = process_photo(s["folder"] / cover, out / "photos" / s["slug"])
            name = data["sizes"][0][1]
            thumb = f'<img class="row-thumb" src="photos/{s["slug"]}/{esc(name)}" alt="" width="{data["w"]}" height="{data["h"]}" loading="lazy">'
        key = lambda text: re.sub(r"[^a-z0-9]+", "-", text.lower())
        rows.append(f"""<a class="story-row" href="stories/{s["slug"]}.html" data-country="{key(s["country"])}" data-place="{key(s["place"])}">
<span class="row-meta"><strong>{esc(s["place"])}</strong><span>{esc(s["country"])}</span><span>{s["minutes"]} min read</span></span>
<span><h2 class="row-title">{esc(s["title"])}</h2><p class="row-dek">{inline(s["dek"])}</p></span>
{thumb}
</a>""")
    next_up = ""
    if config.get("upcoming"):
        names = ", ".join(u["place"] for u in config["upcoming"])
        next_up = f'<p class="next-up">Next on the map: {esc(names)}. Story coming.</p>'
    body = f"""{masthead(config, "")}
<main id="main">
<div class="wrap">
<section class="hero"><h1>{esc(config["headline"])}<span class="and">{esc(config["subline"])}</span></h1></section>
<section class="atlas" id="map" aria-label="Map of the places I have written about">
<div class="map-stage">
<canvas id="typed-map" aria-hidden="true"></canvas>
<div id="map-pins"></div>
<div class="map-hover" id="map-hover" aria-hidden="true" hidden></div>
<a id="map-back" href="#all" hidden>&larr; Back to the world</a>
</div>
<div class="legend">
<p>Choose a number to travel there. Every country is typed from its own name. Bold countries have stories, and faded letters are where it is night right now.</p>
<div class="legend-side"><p id="local-time"></p><p id="map-typing" aria-hidden="true"></p></div>
</div>
</section>
<section class="index" id="stories" aria-label="All stories">
<div class="index-head">
<div class="chips" id="chips"></div>
<button type="button" id="surprise">Surprise me</button>
</div>
<div id="list-status" role="status"></div>
{"".join(rows)}
{next_up}
</section>
<section class="about" id="about">
<h2>About</h2>
<div><p>{inline(config["about"])}</p></div>
</section>
<footer class="foot">{esc(stats(stories, config.get("upcoming")))}.</footer>
</div>
</main>"""
    data = {
        "upcoming": config.get("upcoming", []),
        "stories": [{"place": s["place"], "country": s["country"], "lat": s["lat"], "lon": s["lon"], "tz": s["tz"],
                     "url": f'stories/{s["slug"]}.html'} for s in stories],
    }
    text = page(config["name"], config["description"], "", body, data, ["land.js", "map.js", "site.js"])
    (out / "index.html").write_text(text, encoding="utf-8")


def build_story(config, stories, i, out):
    s = stories[i]
    same_place = [x for x in stories if x["place"] == s["place"]]
    part = same_place.index(s) + 1
    blocks = s["blocks"]
    hero = ""
    if blocks and blocks[0]["kind"] == "photos" and len(blocks[0]["photos"]) == 1:
        first = blocks[0]["photos"][0]
        figure = picture(first, s, out, "../", "(max-width: 1240px) 100vw, 1128px", eager=True)
        if first["aspect"] >= 1.1:
            hero = f'<div class="wrap hero-photo">{figure}</div>'
            blocks = blocks[1:]
    content = "\n".join(render_block(b, s, out, "../") for b in blocks)
    part_text = f'Part {part} of {len(same_place)}' if len(same_place) > 1 else ""
    prev_link = next_link = "<span></span>"
    if i > 0:
        p = stories[i - 1]
        prev_link = f'<a href="{p["slug"]}.html"><span class="label">&larr; Previous story</span><span class="title">{esc(p["title"])}</span></a>'
    if i < len(stories) - 1:
        n = stories[i + 1]
        next_link = f'<a class="next" href="{n["slug"]}.html"><span class="label">Next story &rarr;</span><span class="title">{esc(n["title"])}</span></a>'
    place_key = re.sub(r"[^a-z0-9]+", "-", s["place"].lower())
    body = f"""<div id="progress" aria-hidden="true"></div>
{masthead(config, "../")}
<main id="main">
<div class="wrap story-head">
<p class="dateline"><strong>{esc(s["place"])}, {esc(s["country"])}</strong><span>{part_text}</span><span>{s["minutes"]} min read</span></p>
<h1>{esc(s["title"])}</h1>
<p class="dek">{inline(s["dek"])}</p>
</div>
{hero}
<div class="wrap story-layout">
<article class="story-body">
{content}
<section class="where">
<h2>Where this happened</h2>
<div class="mini-stage"><canvas data-mini="1" data-lon="{s["lon"]}" data-lat="{s["lat"]}" data-country="{esc(s["country"])}" aria-hidden="true"></canvas></div>
<p class="caption-line"><a href="../index.html#{place_key}">See every story from {esc(s["place"])} on the map</a></p>
</section>
<div class="story-foot"><button type="button" id="share">Send this story to someone</button></div>
</article>
</div>
<div class="wrap"><nav class="pager" aria-label="More stories">{prev_link}{next_link}</nav></div>
</main>
<dialog id="viewer" aria-label="Photo viewer">
<img alt="">
<div class="viewer-caption"></div>
<div class="viewer-bar">
<button type="button" class="viewer-prev">&larr; Back</button>
<button type="button" class="viewer-next">Next &rarr;</button>
<button type="button" class="viewer-close">Close</button>
</div>
</dialog>"""
    text = page(f'{s["title"]} | {config["name"]}', s["dek"], "../", body, {},
                ["land.js", "map.js", "site.js"])
    (out / "stories" / f'{s["slug"]}.html').write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", default=str(ROOT / "content"))
    parser.add_argument("--out", default=str(ROOT / "docs"))
    args = parser.parse_args()
    content, out = Path(args.content), Path(args.out)
    config = json.loads((content / "site.json").read_text(encoding="utf-8"))
    stories = [parse_story(p) for p in sorted((content / "stories").glob("*/story.md"))]
    (out / "stories").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)
    for name in ("style.css", "map.js", "site.js", "land.js"):
        shutil.copy(ROOT / "src" / name, out / "assets" / name)
    (out / ".nojekyll").write_text("")
    build_home(config, stories, out)
    for i in range(len(stories)):
        build_story(config, stories, i, out)
    print(f'Built {len(stories)} stories into {out}. {stats(stories, None)}.')


if __name__ == "__main__":
    main()
