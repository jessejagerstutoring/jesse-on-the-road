# Jesse on the Road

A personal travel blog. Jesse sends a story (often in Dutch) and photos; Claude puts it on the site.

## Adding a story

1. Create `content/stories/NN-short-slug/` (NN continues the numbering, in travel order).
2. Copy Jesse's photos into that folder.
3. Write `story.md`, following an existing story for the format.
4. Run `python3 -I build.py`, which writes the site to `docs/`.
5. Commit and push to `main` when Jesse asks. GitHub Pages publishes `docs/` automatically. Original photos stay off GitHub (see `.gitignore`), because they can contain GPS data; only the cleaned copies in `docs/photos/` are published.

The header needs `title`, `dek`, `place`, `country`, `lat`, `lon` and `tz`. A new place appears on the map by itself.
Move a place out of `upcoming` in `content/site.json` once its first story is live.

## Body format

Blocks are separated by a blank line:

- A plain paragraph. `*word*` makes italics.
- `![Caption](photo.jpg)` on its own: a landscape runs wide, a portrait stays modest. If it comes first and is landscape, it becomes the story's opening photo.
- Several photo lines with no blank line between them share a row at their true proportions.
- `> Pull quote`, `***` for a section break, `::: Field notes` followed by `- ` lines for tips.
- `placeholder-16x9` as a file name marks an empty frame. Replace these with real photos.

## Writing

- English, in Jesse's own voice: warm, chatty, self-mocking, with "of course" and "anyway". Tidy the language, but do not make it sound corporate or add events, facts or opinions that Jesse did not write.
- Title: short and hooky. Dek: one sentence that makes you want to read on. Short paragraphs.
- Field notes contain only what the story itself supports.
- Show Jesse any new titles and anything sensitive about other people before it goes online.

## Design

Black ink on white paper by default, with an optional dark mode, and colour only in photos. The typed map stays at the centre of the home page with the stories straight under it. Every country on it is typed from its own name, and `country` in a story must match the map's name for that country (for example `United States`). Keep titles compact, not extra-wide. No drawn illustrations: the look must not feel cartoonish. Fonts: Archivo (headlines), Newsreader (reading), Courier Prime (labels). The site must work for someone's grandmother, on phones and tablets, and in Safari. Test in WebKit.

## Files

`build.py` makes the site. `src/` holds the CSS, JavaScript and map data. `tools/upright.swift` turns photos the right way up. `tools/make_land.py` made the map data and only needs running again if the map source changes. `ontwerpen/` holds the earlier design concepts and is not part of the site.
