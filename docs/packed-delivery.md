# Packed delivery format (notes-packed-1)

Goal: **store heavy, deliver light**. The repo keeps the full data; the client
fetches only the part it is looking at. Built for the score+part dual-read
workflow — score notes and part notes share one packed layout, so the same
shard machinery serves both.

## Why the current layout is heavy

`public/reader/data/<id>.json` is a monolith: every system image is an inline
PNG data-URI (~88% of bytes) and every note is an object with full key names.
Measured on committed data:

| Part | Monolith | Notes share | Images share | Objects→rows |
| --- | --- | --- | --- | --- |
| dvorak8-trombone1 | 1044 KB | 131 KB (574 ev, 229 B/ev) | 932 KB | → 40 B/ev |
| dvorak8-horn2 | 2885 KB | (921 ev) | 2003 KB | → 41 B/ev |
| verdi-nabucco-trombone2 | 1419 KB | (492 ev) | 981 KB | → 40 B/ev |
| dvorak8-horn3-mvt3 | 419 KB | (57 ev) | 299 KB | → 43 B/ev |

Two independent savings:

1. **Note packing**: rows over shared dictionaries → ~40 B/event (5.7×).
2. **Image extraction**: inline data-URIs → `img/<sys>.png` files fetched when
   that system scrolls into view. Base64 decode cost disappears and images
   cache individually.

PNG kept on purpose: re-encoding the line-art strips to WebP q60 ballooned to
268% — lossless palette PNG beats lossy WebP on this content.

## Layout

```
data/<id>/
  manifest.json     metadata, dictionaries, system descriptors (img -> path)
  notes/<shard>.json
  img/<sys>.png
```

### manifest.json

Everything except `notes` and pixel payloads, plus:

- `schema: "notes-packed-1"`
- `dicts`: `{mvt, dur, off, p, trip, key, pos, unc}` — ordered value tables.
  `trip` entries are `[letter, octave, position]` triples shared by the `w`,
  `f`, `snd` fields.
- `cols`: fixed row layout `s,mvt,bar,x,y,dur,off,flags,p,w,f,snd,key,pos,unc`.
- `notes_shards`: `{shard: "notes/<shard>.json"}`.
- `systems[].img`: `"img/007.png"` instead of a data-URI.

### Packed rows

`[s, mvt, bar, x, y, dur, off, flags, p, w, f, snd, key, pos, unc]` — every
non-numeric field is a dictionary index. `off` is beats×16 (quantised int).
`flags` bitfield: 1=tie, 2=old, 4=sim, 8=unc-set. `id` is the row index, not
stored. Empty `unc` rows still carry flag 8 so review state survives the
round trip.

### Shards — "該当部分だけ読み込む"

- **Parts** (`--shard system`): one notes file per system (~0.5 KB each on
  trombone1). Client flow: fetch manifest (~10–50 KB) → render from
  `systems[]` geometry → fetch `notes/sNNN.json` + `img/NNN.png` only for
  systems in view. First paint ≈ manifest + ~1 shard + ~1 image ≈ **2–5% of
  the monolith** (trombone1: ~46 KB vs 1044 KB; horn2: ~75 KB vs 2885 KB).
- **Score** (`--shard page`): one notes file per pdf page, aligned with the
  already lazy-loaded `pages/pNNN.webp`. Open page → fetch page image +
  `notes/pNNN.json` (~5–15 KB at score scale). The instrument filter is
  client-side on the staff row index `s`; no per-instrument fetches needed.
- **all**: single notes file, for tooling that wants the whole part.

## Size projection at score scale

Dvořák 8 ≈ 30k note events → ~1.2 MB packed total (~7 KB/page shard,
~0.4 MB gzipped whole). Per open page the client fetches ~200 KB WebP +
~7 KB notes. The score note layer is the cheap half of the dual-read: the
part pipeline already produces the richer data.

## Round trip / consumption

`tools/dynamic/pack_notes.py <data.json> --out <dir> --shard system|page|all`
emits the layout and prints the size table. Unpacking is ~30 lines of JS:
index into `dicts`, expand flags, renumber `id`. Until the reader speaks the
format, emit packed dirs alongside canonical `data/<id>.json` — never instead
of it, so the generated contract stays single-source.

## Committing crop images

Decision: **system/staff crop images are committed as files**, not only
embedded in generated JSON. Rationale:

- Policy fit: AGENTS.md bans raw page scans and source PDFs, not derivatives.
  Crops are the same derivative class as the images already embedded in
  `data/<id>.json` and the deskewed WebP pages under `public/score/<id>/`.
- Delivery: files are ~25% smaller than their base64 form, fetchable per
  system (the shard granularity), and cache/CDN-friendly.
- Reproducibility: once crops are committed, `build_reader.py`/`pack_notes.py`
  run without the (uncommitted) source PDF — the repo becomes self-contained
  for rebuilding delivery artifacts.

Layout and granularity:

- Canonical store: `project/<composer>/<work>/<part>/dynamic/img/sys_NNN.png`
  (per staff row for parts; per system band for the score), emitted next to
  `notes_pNN.json`/`bars_pNN.json`.
- Emit step copies them into `data/<id>/img/` in the packed layout; the
  monolith `data/<id>.json` keeps inline images until the reader switches.
- Compression: PNG for line art (measured winner over WebP q60); re-evaluate
  WebP-lossless/q80 when the corpus exists. Total estimate: parts ~20–60 MB,
  full score ~80–240 MB depending on band granularity — acceptable under
  "store heavy" as long as delivery stays sharded.

Decode agents keep writing JSON only; crops are produced by the build/pack
step (clean crops — no guide lines) so review artifacts stay readable.

## Open pieces

- Reader/score-viewer support: lazy `img`/`notes` fetches keyed on visible
  systems; per-page notes fetch on score page open.
- `build_reader.py` / `build_score.py` emit the packed layout next to the
  monolith (opt-in flag).
- Score dual-read: score shards + part shards give the auto-diff layer two
  independent compact sources to compare.
