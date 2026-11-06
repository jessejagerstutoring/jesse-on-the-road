# Jesse's Travels

A personal travel blog. Jesse sends a story (often in Dutch) and photos; Claude puts it on the site.

## Adding a story

Every story must go on the site in both English and Dutch. The build stops if a language is missing.

1. Create `content/stories/NN-short-slug/` (NN continues the numbering, in travel order; the slug is English).
2. Copy Jesse's photos into that folder.
3. Write `story.nl.md`: Jesse's own Dutch text, with only obvious typos fixed and long paragraphs split.
4. Write `story.md`: the English version, with the same photos in the same order.
5. Run `python3 -I build.py`, which writes English to `docs/` and Dutch to `docs/nl/`.
6. Commit and push to `main` when Jesse asks. GitHub Pages publishes `docs/` automatically. Original photos stay off GitHub (see `.gitignore`), because they can contain GPS data; only the cleaned copies in `docs/photos/` are published.

The header of `story.md` needs `title`, `dek`, `place`, `country`, `lat`, `lon`, `tz` and `date` (the day it goes on the site, like `2026-11-04`). `country` must be the English map name (for example `United States`). The header of `story.nl.md` needs `title`, `dek`, `place` and `country`, in Dutch. A new place appears on the map by itself.
Fill in `contact` (Instagram name without @, and email) in `content/site.json` to show the message box under every story and in About.
Fill in `newsletter.action` (the sign-up form address from the mailing service) and `newsletter.field` (its email field name) to show the sign-up form.
Move a place out of `upcoming` in `content/site.json` once its first story is live.

## Body format

Blocks are separated by a blank line:

- A plain paragraph. `*word*` makes italics.
- `![Caption](photo.jpg)` on its own: a landscape runs wide, a portrait stays modest. If it comes first and is landscape, it becomes the story's opening photo.
- Several photo lines with no blank line between them share a row at their true proportions.
- `> Pull quote`, `***` for a section break, `::: Field notes` (Dutch: `::: Reisnotities`) followed by `- ` lines for tips.
- `placeholder-16x9` as a file name marks an empty frame. Replace these with real photos.

## Writing

- Dutch: Jesse's original words. English: the same story in Jesse's voice, warm, chatty and self-mocking, with "of course" and "anyway". Tidy the language, but do not make it sound corporate or add events, facts or opinions that Jesse did not write.
- Title: short and hooky. Dek: one sentence that makes you want to read on. Short paragraphs.
- Field notes contain only what the story itself supports.
- Show Jesse any new titles and anything sensitive about other people before it goes online.

## Design

Black ink on white paper by default, with an optional dark mode, and colour only in photos. The typed map stays at the centre of the home page with the stories straight under it. Every country on it is typed from its own name, in the language of the page. Keep titles compact, not extra-wide. No drawn illustrations: the look must not feel cartoonish. Fonts: Archivo (headlines), Newsreader (reading), Courier Prime (labels). Interface text lives in `STRINGS` in `build.py`, in both languages. The site must work for someone's grandmother, on phones and tablets, and in Safari. Test in WebKit.

## Files

`build.py` makes the site. `src/` holds the CSS, JavaScript and map data. `tools/upright.swift` turns photos the right way up. `tools/countries_nl.json` holds the Dutch country names. `tools/make_land.py` made the map data and only needs running again if the map source changes. `ontwerpen/` holds the earlier design concepts and is not part of the site.
