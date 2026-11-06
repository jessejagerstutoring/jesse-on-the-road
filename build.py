#!/usr/bin/env python3
"""Builds the website into docs/ from the stories in content/.

    python3 -I build.py                    build everything
    python3 -I build.py --content DIR --out DIR   build from other folders (for testing)

No installs needed: it uses Python and macOS's own image tools (sips and ImageIO).
Photos are resized for phones, tablets and big screens, turned the right way up, and
stripped of hidden metadata, so a photo never reveals its GPS location.
"""
import argparse, base64, datetime, html, json, re, shutil, subprocess, sys, tempfile
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


def key_of(name):
    """The name that identifies a place or country in links, the same in both languages."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_story(path, lang, base=None):
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not match:
        sys.exit(f"{path} needs a --- header at the top")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    required = ("title", "dek", "place", "country") + (() if base else ("lat", "lon", "tz", "date"))
    for key in required:
        if key not in meta:
            sys.exit(f"{path} is missing '{key}' in its header")
    if base:
        meta.update(lat=base["lat"], lon=base["lon"], tz=base["tz"], date=base["date"], key_place=base["key_place"],
                    key_country=base["key_country"], country_en=base["country_en"])
    else:
        try:
            meta["date"] = datetime.date.fromisoformat(meta["date"])
        except ValueError:
            sys.exit(f"{path}: date must look like 2026-11-04 (year-month-day)")
        meta.update(lat=float(meta["lat"]), lon=float(meta["lon"]), key_place=key_of(meta["place"]),
                    key_country=key_of(meta["country"]), country_en=meta["country"])
    meta["lang"] = lang
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
        return (f'<figure><div class="placeholder" style="aspect-ratio:{ratio[0]}/{ratio[1]}">{esc(STRINGS[story["lang"]]["photo_here"])}</div>'
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


STRINGS = {
    "en": {
        "skip": "Skip to the stories", "menu": "Main menu", "map": "The map", "about": "About",
        "larger": "Larger text", "smaller": "Smaller text", "dark": "Dark mode", "light": "Light mode",
        "other": "Nederlands", "map_label": "Map of the places I have written about",
        "back_world": "Back to the world",
        "legend": "Choose a number to travel there. Every country is typed from its own name. Bold countries have stories, and faded letters are where it is night right now.",
        "all_stories": "All stories", "surprise": "Surprise me",
        "next_up": "Next on the map: {names}. Story coming.", "min_read": "{n} min read", "part": "Part {a} of {b}",
        "where": "Where this happened", "every": "See every story from {place} on the map",
        "share": "Send this story to someone", "copied": "Link copied", "more": "More stories",
        "prev": "Previous story", "next": "Next story",
        "viewer": "Photo viewer", "back": "Back", "forward": "Next", "close": "Close",
        "photo_here": "Your photo goes here", "story_coming": ", story coming",
        "story": "story", "stories": "stories", "from": "from", "world": "the world", "of": "of",
        "time": "It is {time} in {place} right now.", "typing": "Now typing: {name}",
        "stats": "{stories}, {countries}, {places}, {minutes} minutes of reading",
        "country": "country", "countries": "countries", "place": "place", "places": "places",
        "ask": "A question, a tip or just a reaction? Send me a message. I read everything.",
        "contact": "Send me a message", "instagram": "Message me on Instagram", "email": "Send me an email",
        "email_subject": "About {title}",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"],
        "news_title": "Come along on the trip",
        "news_text": "Leave your email and now and then you'll get a short update from me: where I am, and the newest stories.",
        "news_label": "Your email address", "news_button": "Sign me up",
        "news_small": "Only for these updates. You can unsubscribe at any time.",
    },
    "nl": {
        "skip": "Naar de verhalen", "menu": "Hoofdmenu", "map": "De kaart", "about": "Over mij",
        "larger": "Grotere tekst", "smaller": "Kleinere tekst", "dark": "Donkere modus", "light": "Lichte modus",
        "other": "English", "map_label": "Kaart van de plekken waarover ik heb geschreven",
        "back_world": "Terug naar de wereld",
        "legend": "Kies een nummer om erheen te reizen. Elk land is getypt uit zijn eigen naam. Vetgedrukte landen hebben verhalen, en vervaagde letters staan waar het nu nacht is.",
        "all_stories": "Alle verhalen", "surprise": "Verras me",
        "next_up": "Volgende op de kaart: {names}. Verhaal volgt.", "min_read": "{n} min lezen", "part": "Deel {a} van {b}",
        "where": "Waar dit gebeurde", "every": "Bekijk alle verhalen uit {place} op de kaart",
        "share": "Stuur dit verhaal door", "copied": "Link gekopieerd", "more": "Meer verhalen",
        "prev": "Vorig verhaal", "next": "Volgend verhaal",
        "viewer": "Foto's bekijken", "back": "Terug", "forward": "Volgende", "close": "Sluiten",
        "photo_here": "Hier komt je foto", "story_coming": ", verhaal volgt",
        "story": "verhaal", "stories": "verhalen", "from": "uit", "world": "de hele wereld", "of": "van",
        "time": "Het is nu {time} in {place}.", "typing": "Nu aan het typen: {name}",
        "stats": "{stories}, {countries}, {places}, {minutes} minuten leestijd",
        "country": "land", "countries": "landen", "place": "plek", "places": "plekken",
        "ask": "Een vraag, een tip of gewoon een reactie? Stuur me een bericht. Ik lees alles.",
        "contact": "Stuur me een bericht", "instagram": "Stuur een bericht via Instagram", "email": "Stuur me een e-mail",
        "email_subject": "Over {title}",
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
                   "oktober", "november", "december"],
        "news_title": "Reis met me mee",
        "news_text": "Laat je e-mailadres achter en je krijgt af en toe een korte update van mij: waar ik nu ben, en de nieuwste verhalen.",
        "news_label": "Je e-mailadres", "news_button": "Schrijf me in",
        "news_small": "Alleen voor deze updates. Afmelden kan altijd.",
    },
}
BROWSER_STRINGS = ("larger", "smaller", "dark", "light", "story_coming", "story", "stories", "from", "world",
                   "of", "time", "typing", "share", "copied", "all_stories")


def browser_strings(lang):
    return {k: STRINGS[lang][k] for k in BROWSER_STRINGS}


def page(lang, config, title, description, root, local, alternate, path, body, data):
    """One full HTML page. `alternate` links to this same page in the other language."""
    tags = "".join(f'<script src="{root}assets/{name}"></script>' for name in ("land.js", "map.js", "site.js"))
    base = config["url"]
    en_url, nl_url = base + path, base + "nl/" + path
    # A Dutch browser goes to the Dutch page, unless the visitor chose a language themselves.
    redirect = ""
    if lang == "en":
        redirect = ("<script>try{if(!/[?&]lang=/.test(location.search)){var s=localStorage.getItem('lang');"
                    "if(s==='nl'||(!s&&/^nl/i.test(navigator.language||''))){location.replace('" + alternate +
                    "'+location.hash)}}}catch(e){}</script>\n")
    t = STRINGS[lang]
    other = "nl" if lang == "en" else "en"
    data = dict(data, lang=lang, t=browser_strings(lang))
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#ffffff">
<link rel="alternate" hreflang="en" href="{esc(en_url)}">
<link rel="alternate" hreflang="nl" href="{esc(nl_url)}">
{redirect}<script>try{{if(localStorage.getItem('theme')==='dark')document.documentElement.setAttribute('data-theme','dark')}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<a class="skip" href="#main">{esc(t["skip"])}</a>
<header class="top wrap">
<a class="brand" href="{local}index.html">{esc(config[lang]["name"])}</a>
<nav aria-label="{esc(t["menu"])}">
<a href="{local}index.html#all">{esc(t["map"])}</a>
<a href="{local}index.html#about">{esc(t["about"])}</a>
<button type="button" class="link-button" id="text-size" aria-pressed="false">{esc(t["larger"])}</button>
<button type="button" class="link-button" id="theme">{esc(t["dark"])}</button>
<a id="language" data-lang="{other}" lang="{other}" hreflang="{other}" href="{esc(alternate)}?lang={other}">{esc(t["other"])}</a>
</nav>
</header>
{body}
<script>window.SITE={json.dumps(data, ensure_ascii=False).replace("</", "<\\/")};</script>
{tags}
</body>
</html>
"""


def contact_box(config, lang, subject=""):
    """Ways to send Jesse a message, shown only once an Instagram name or email is filled in."""
    from urllib.parse import quote
    t = STRINGS[lang]
    contact = config.get("contact", {})
    handle = contact.get("instagram", "").strip().lstrip("@")
    email = contact.get("email", "").strip()
    links = []
    if handle:
        links.append(f'<a class="contact-link" href="https://ig.me/m/{quote(handle)}" rel="noopener">{esc(t["instagram"])}</a>')
    if email:
        query = f"?subject={quote(subject)}" if subject else ""
        links.append(f'<a class="contact-link" href="mailto:{esc(email)}{query}">{esc(t["email"])}</a>')
    if not links:
        return ""
    return (f'<section class="contact" aria-label="{esc(t["contact"])}"><p>{esc(t["ask"])}</p>'
            f'<div class="contact-links">{"".join(links)}</div></section>')


def nice_date(day, lang):
    return f'{day.day} {STRINGS[lang]["months"][day.month - 1]} {day.year}'


def newsletter_box(config, lang):
    """A sign-up form for the update mail, shown only once a mailing service's form address is filled in."""
    news = config.get("newsletter", {})
    action = news.get("action", "").strip()
    if not action.startswith("https://"):
        return ""
    t = STRINGS[lang]
    field = news.get("field", "email")
    return f"""<section class="newsletter" aria-labelledby="news-title-{lang}">
<h2 id="news-title-{lang}">{esc(t["news_title"])}</h2>
<p>{esc(t["news_text"])}</p>
<form action="{esc(action)}" method="post" target="_blank">
<label for="news-email-{lang}">{esc(t["news_label"])}</label>
<div class="news-row"><input id="news-email-{lang}" type="email" name="{esc(field)}" autocomplete="email" required>
<button type="submit">{esc(t["news_button"])}</button></div>
</form>
<p class="news-small">{esc(t["news_small"])}</p>
</section>"""


def count(n, one, many):
    return f"{n} {one if n == 1 else many}"


def stats(stories, lang):
    t = STRINGS[lang]
    return t["stats"].format(
        stories=count(len(stories), t["story"], t["stories"]),
        countries=count(len({s["key_country"] for s in stories}), t["country"], t["countries"]),
        places=count(len({s["key_place"] for s in stories}), t["place"], t["places"]),
        minutes=sum(s["minutes"] for s in stories),
    )


def build_home(config, stories, lang, out):
    t = STRINGS[lang]
    text_config = config[lang]
    root = "" if lang == "en" else "../"
    rows = []
    for s in stories:
        thumb = ""
        cover = s.get("cover") or next((p["file"] for b in s["blocks"] if b["kind"] == "photos"
                                        for p in b["photos"] if not placeholder_ratio(p["file"])), None)
        if cover:
            data = process_photo(s["folder"] / cover, out / "photos" / s["slug"])
            name = data["sizes"][0][1]
            thumb = f'<img class="row-thumb" src="{root}photos/{s["slug"]}/{esc(name)}" alt="" width="{data["w"]}" height="{data["h"]}" loading="lazy">'
        rows.append(f"""<a class="story-row" href="stories/{s["slug"]}.html" data-country="{s["key_country"]}" data-place="{s["key_place"]}">
<span class="row-meta"><strong>{esc(s["place"])}</strong><span>{esc(s["country"])}</span><time datetime="{s["date"].isoformat()}">{esc(nice_date(s["date"], lang))}</time><span>{esc(t["min_read"].format(n=s["minutes"]))}</span></span>
<span><h2 class="row-title">{esc(s["title"])}</h2><p class="row-dek">{inline(s["dek"])}</p></span>
{thumb}
</a>""")
    upcoming = [dict(u, **u.get(lang, {}), en_place=u["place"], en_country=u["country"]) for u in config.get("upcoming", [])]
    next_up = ""
    if upcoming:
        next_up = f'<p class="next-up">{esc(t["next_up"].format(names=", ".join(u["place"] for u in upcoming)))}</p>'
    body = f"""<main id="main">
<div class="wrap">
<section class="hero"><h1>{esc(text_config["headline"])}<span class="and">{esc(text_config["subline"])}</span></h1></section>
<section class="atlas" id="map" aria-label="{esc(t["map_label"])}">
<div class="map-stage">
<canvas id="typed-map" aria-hidden="true"></canvas>
<div id="map-pins"></div>
<div class="map-hover" id="map-hover" aria-hidden="true" hidden></div>
<a id="map-back" href="#all" hidden>&larr; {esc(t["back_world"])}</a>
</div>
<div class="legend">
<p>{esc(t["legend"])}</p>
<div class="legend-side"><p id="local-time"></p><p id="map-typing" aria-hidden="true"></p></div>
</div>
</section>
<section class="index" id="stories" aria-label="{esc(t["all_stories"])}">
<div class="index-head">
<div class="chips" id="chips"></div>
<button type="button" id="surprise">{esc(t["surprise"])}</button>
</div>
<div id="list-status" role="status"></div>
{"".join(rows)}
{next_up}
</section>
{newsletter_box(config, lang)}
<section class="about" id="about">
<h2>{esc(t["about"])}</h2>
<div><p>{inline(text_config["about"])}</p>{contact_box(config, lang)}</div>
</section>
<footer class="foot">{esc(stats(stories, lang))}.</footer>
</div>
</main>"""
    data = {
        "upcoming": [{"place": u["place"], "country": u["country"], "lat": u["lat"], "lon": u["lon"], "tz": u["tz"],
                      "keyPlace": key_of(config_name(u, "place")), "keyCountry": key_of(config_name(u, "country"))}
                     for u in upcoming],
        "stories": [{"place": s["place"], "country": s["country"], "countryEn": s["country_en"], "lat": s["lat"],
                     "lon": s["lon"], "tz": s["tz"], "keyPlace": s["key_place"], "keyCountry": s["key_country"],
                     "url": f'stories/{s["slug"]}.html'} for s in stories],
    }
    alternate = "nl/index.html" if lang == "en" else "../index.html"
    html_text = page(lang, config, text_config["name"], text_config["description"], root, "", alternate, "", body, data)
    folder = out if lang == "en" else out / "nl"
    (folder / "index.html").write_text(html_text, encoding="utf-8")


def config_name(entry, field):
    """The English name of an upcoming place. It stays the key in both languages."""
    return entry.get("en_" + field, entry[field])


def build_story(config, stories, i, lang, out):
    t = STRINGS[lang]
    s = stories[i]
    root = "../" if lang == "en" else "../../"
    same_place = [x for x in stories if x["key_place"] == s["key_place"]]
    part = same_place.index(s) + 1
    blocks = s["blocks"]
    hero = ""
    if blocks and blocks[0]["kind"] == "photos" and len(blocks[0]["photos"]) == 1:
        first = blocks[0]["photos"][0]
        figure = picture(first, s, out, root, "(max-width: 1240px) 100vw, 1128px", eager=True)
        if first["aspect"] >= 1.1:
            hero = f'<div class="wrap hero-photo">{figure}</div>'
            blocks = blocks[1:]
    content = "\n".join(render_block(b, s, out, root) for b in blocks)
    part_text = t["part"].format(a=part, b=len(same_place)) if len(same_place) > 1 else ""
    prev_link = next_link = "<span></span>"
    if i > 0:
        p = stories[i - 1]
        prev_link = f'<a href="{p["slug"]}.html"><span class="label">&larr; {esc(t["prev"])}</span><span class="title">{esc(p["title"])}</span></a>'
    if i < len(stories) - 1:
        n = stories[i + 1]
        next_link = f'<a class="next" href="{n["slug"]}.html"><span class="label">{esc(t["next"])} &rarr;</span><span class="title">{esc(n["title"])}</span></a>'
    body = f"""<div id="progress" aria-hidden="true"></div>
<main id="main">
<div class="wrap story-head">
<p class="dateline"><strong>{esc(s["place"])}, {esc(s["country"])}</strong><time datetime="{s["date"].isoformat()}">{esc(nice_date(s["date"], lang))}</time><span>{esc(part_text)}</span><span>{esc(t["min_read"].format(n=s["minutes"]))}</span></p>
<h1>{esc(s["title"])}</h1>
<p class="dek">{inline(s["dek"])}</p>
</div>
{hero}
<div class="wrap story-layout">
<article class="story-body">
{content}
<section class="where">
<h2>{esc(t["where"])}</h2>
<div class="mini-stage"><canvas data-mini="1" data-lon="{s["lon"]}" data-lat="{s["lat"]}" data-country="{esc(s["country_en"])}" aria-hidden="true"></canvas></div>
<p class="caption-line"><a href="../index.html#{s["key_place"]}">{esc(t["every"].format(place=s["place"]))}</a></p>
</section>
<div class="story-foot"><button type="button" id="share">{esc(t["share"])}</button></div>
{contact_box(config, lang, t["email_subject"].format(title=s["title"]))}
{newsletter_box(config, lang)}
</article>
</div>
<div class="wrap"><nav class="pager" aria-label="{esc(t["more"])}">{prev_link}{next_link}</nav></div>
</main>
<dialog id="viewer" aria-label="{esc(t["viewer"])}">
<img alt="">
<div class="viewer-caption"></div>
<div class="viewer-bar">
<button type="button" class="viewer-prev">&larr; {esc(t["back"])}</button>
<button type="button" class="viewer-next">{esc(t["forward"])} &rarr;</button>
<button type="button" class="viewer-close">{esc(t["close"])}</button>
</div>
</dialog>"""
    alternate = f'../nl/stories/{s["slug"]}.html' if lang == "en" else f'../../stories/{s["slug"]}.html'
    html_text = page(lang, config, f'{s["title"]} | {config[lang]["name"]}', s["dek"], root, "../", alternate,
                     f'stories/{s["slug"]}.html', body, {})
    folder = out / "stories" if lang == "en" else out / "nl" / "stories"
    (folder / f'{s["slug"]}.html').write_text(html_text, encoding="utf-8")


def real_photos(story):
    return {p["file"] for b in story["blocks"] if b["kind"] == "photos" for p in b["photos"]
            if not placeholder_ratio(p["file"])}


def load_stories(content):
    """Every story must exist in both languages, with the same photos, on a country the map knows."""
    land = (ROOT / "src" / "land.js").read_text(encoding="utf-8")
    map_names = json.loads(re.search(r"names:(\[.*?\]),nl:", land).group(1))
    english, dutch = [], []
    for path in sorted((content / "stories").glob("*/story.md")):
        en = parse_story(path, "en")
        if en["country"] not in map_names:
            sys.exit(f'{path}: country "{en["country"]}" is not a name on the map. Use the English name from src/land.js.')
        nl_path = path.with_name("story.nl.md")
        if not nl_path.exists():
            sys.exit(f"{path.parent} has no Dutch version. Add story.nl.md.")
        nl = parse_story(nl_path, "nl", base=en)
        if real_photos(en) != real_photos(nl):
            sys.exit(f"{path.parent}: the English and Dutch stories use different photos: "
                     f"{sorted(real_photos(en) ^ real_photos(nl))}")
        english.append(en)
        dutch.append(nl)
    return {"en": english, "nl": dutch}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", default=str(ROOT / "content"))
    parser.add_argument("--out", default=str(ROOT / "docs"))
    args = parser.parse_args()
    content, out = Path(args.content), Path(args.out)
    config = json.loads((content / "site.json").read_text(encoding="utf-8"))
    stories = load_stories(content)
    for folder in (out / "stories", out / "nl" / "stories", out / "assets"):
        folder.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "map.js", "site.js", "land.js"):
        shutil.copy(ROOT / "src" / name, out / "assets" / name)
    (out / ".nojekyll").write_text("")
    for lang, items in stories.items():
        build_home(config, items, lang, out)
        for i in range(len(items)):
            build_story(config, items, i, lang, out)
        print(f"{lang}: {stats(items, lang)}.")
    print(f"Built into {out}")


if __name__ == "__main__":
    main()
