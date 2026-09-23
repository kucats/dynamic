"""Non-obscuring score derivatives: standalone HTML, PDF and tabular data."""

from __future__ import annotations

import base64
import csv
import html
import io
import json
from pathlib import Path

from .score import pitch_info
from .workflow import local_path, read_json, sha256


def lane_labels(notes: list[dict], scale: float, measure, gap: float) -> tuple[list[tuple], int]:
    ends, labels = [], []
    for note in notes:
        x = note["x"] * scale
        half = measure(note["display_pitch"]) / 2
        lane = next((i for i, end in enumerate(ends) if x - half > end + gap), len(ends))
        if lane == len(ends):
            ends.append(0)
        ends[lane] = x + half
        labels.append((note, lane))
    return labels, max(1, len(ends))


def source_rows(root: Path, pages: dict, project: dict):
    from PIL import Image

    for page, systems in pages.items():
        item = project["source"]["images"][page]
        with Image.open(local_path(root, item["path"])) as original:
            source = original.convert("L")
        if list(source.size) != [item["width"], item["height"]]:
            raise ValueError("Source image dimensions differ from manifest")
        layout = project.get("layout", {}).get("pages", {}).get(page, {})
        x0, x1 = layout.get("crop_x", [0, source.width])
        if not 0 <= x0 < x1 <= source.width:
            raise ValueError("Invalid horizontal score crop")
        if "cuts" in layout:
            cuts = layout["cuts"]
        else:
            cuts = [0]
            for previous, following in zip(systems, systems[1:]):
                lower = int(max(y for _, y in previous["lines"][4])) + 1
                upper = int(min(y for _, y in following["lines"][0])) - 1
                if upper <= lower:
                    raise ValueError("Overlapping staff systems need explicit layout cuts")
                band = source.crop((x0, lower, x1, upper))
                # Prefer the middle of the longest blank run; retain every source
                # row exactly once, including headings, cues and ledger lines.
                ink = [sum(v < 150 for v in band.crop((0, y, band.width, y + 1)).getdata()) for y in range(band.height)]
                runs, start = [], None
                for y, value in enumerate([*ink, 999999]):
                    if value < 3 and start is None:
                        start = y
                    elif value >= 3 and start is not None:
                        runs.append((start, y))
                        start = None
                cut = sum(max(runs, key=lambda r: r[1] - r[0])) // 2 if runs else min(range(len(ink)), key=ink.__getitem__)
                cuts.append(lower + cut)
            cuts.append(source.height)
        if len(cuts) != len(systems) + 1 or cuts != sorted(set(cuts)) or cuts[0] < 0 or cuts[-1] > source.height:
            raise ValueError("Layout cuts must increase and bound every system")
        for i, system in enumerate(systems):
            y0, y1 = cuts[i:i + 2]
            for note in system["notes"]:
                if not x0 <= note["x"] < x1 or not y0 <= note["y"] < y1:
                    raise ValueError(f"Layout clips note {note['note_id']}; adjust layout cuts")
            yield int(page), system, source.crop((x0, y0, x1, y1)), x0, y0


def html_row(page: int, system: dict, crop, x0: int, y0: int, *, review: bool = False) -> str:
    width, height = crop.size
    y1 = y0 + height
    font = max(16, width * .009)
    labels, lanes = lane_labels(system["notes"], 1, lambda s: len(s) * font * .64, font * .2)
    lane_height = font * 2.2
    buffer = io.BytesIO()
    display_width = min(1900, width)
    crop.resize((display_width, max(1, round(height * display_width / width)))).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    sid = system["system"]
    parts = [f'<section id="p{page}s{sid}"><h2>原譜 {page}ページ / {sid}段目 <span>{len(system["notes"])}音符</span></h2>',
             f'<svg viewBox="{x0} {y0} {width} {height + (lanes + .5) * lane_height}" role="group" aria-label="原譜 {page}ページ {sid}段">',
             f'<image x="{x0}" y="{y0}" width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/>']
    for note, lane in labels:
        x, y = note["x"], note["y"]
        label = html.escape(note["display_pitch"])
        note_id = html.escape(note["note_id"], quote=True)
        yy = y1 + font * 1.2 + lane * lane_height
        position = note.get("position") if note.get("position") is not None else "?"
        grade = note.get("grade")
        score_label = f" / Audiveris grade {grade:.3f}" if grade is not None else ""
        description = (f'{label} / {position}ポジション' if not review else label) + score_label
        parts.extend([f'<g class="note" data-id="{note_id}" tabindex="0" role="button" aria-label="{description}">',
                      f'<title>{note_id}{score_label}</title><rect class="hit" x="{x-32}" y="{y-29}" width="64" height="58"/>',
                      f'<rect class="halo" x="{x-30}" y="{y-28}" width="60" height="56" rx="10"/>',
                      f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{yy-font}"/>',
                      f'<text class="pitch" style="font-size:{font}px" x="{x}" y="{yy}">{label}</text>',
                      f'<text class="pos" style="font-size:{font*.85}px" x="{x}" y="{yy+font}">{position if not review else "candidate"}</text></g>'])
    if not labels:
        parts.append(f'<text class="muted" x="{x0+30}" y="{y1+font*1.5}">休符・合図用の小音符のみ</text>')
    parts.append("</svg></section>")
    return "".join(parts)


def render_candidate_review(root: Path) -> Path:
    project = read_json(root / "project.json")
    candidates = read_json(root / "candidates.json")
    for page, systems in candidates["pages"].items():
        for system in systems:
            for note in system["notes"]:
                note.update(display_pitch=f"{note['id']}: {pitch_info(note['pitch'])[2]}",
                            note_id=f"candidate-p{page}-s{system['system']}-n{note['id']}")
    rows = [html_row(*row, review=True) for row in source_rows(root, candidates["pages"], project)]
    css = Path(__file__).with_name("player.css").read_text()
    title = html.escape(project["title"] + " / " + project["part"])
    path = local_path(root, f"reviews/{sha256(root / 'candidates.json')}/candidates.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<!doctype html><html lang="ja"><meta charset="utf-8"><title>{title} 候補レビュー</title>'
                    f'<style>{css}</style><header><h1>{title} — OMR候補</h1>'
                    '<p>番号はcorrections.jsonの段ごとの候補ID。小音符・欠落・音部記号・調号・臨時記号を原譜に照合してください。</p>'
                    '<p>Audiveris gradeは認識スコアで、音符の正しさを示す確率ではありません。各音を原譜で確認してください。</p>'
                    '<p>これは未確認の候補です。音価はrhythm.jsonへ別途転記します。</p></header><main>'
                    + "".join(rows) + "</main></html>", encoding="utf-8")
    return path


def render_outputs(root: Path, out: Path, data: dict, project: dict, font: Path | None) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    font_name = "Helvetica"
    if font:
        font_name = "FuyomiFont"
        pdfmetrics.registerFont(TTFont(font_name, str(font)))
    elif not (project["title"] + project["part"]).isascii():
        raise ValueError("A Unicode title/part requires --font with a compatible TrueType font")
    pdf = canvas.Canvas(str(out / "reading.pdf"), pagesize=(842, 595), invariant=1)
    pdf.setTitle(project["title"] + " / " + project["part"])
    page_number, top, on_page = 1, 535, False
    layout, webrows = [], []

    def heading():
        pdf.setFillColorRGB(.08, .18, .28)
        pdf.setFont(font_name, 12)
        title = project["title"] + " / " + project["part"]
        size = min(12, 12 * 782 / max(1, pdfmetrics.stringWidth(title, font_name, 12)))
        pdf.setFont(font_name, size)
        pdf.drawString(30, 570, title)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(30, 551, f"Concert pitch (C4 = middle C, H = B natural) / Bb basic slide position / {data['audit']['review_status']}")

    def footer():
        pdf.setFont("Helvetica", 8)
        pdf.drawString(30, 18, "fuyomi | Source noteheads preserved; labels outside the source image | internal bar numbers")
        pdf.drawRightString(812, 18, str(page_number))

    heading()
    for page, system, crop, x0, y0 in source_rows(root, data["pages"], project):
        scale = min(782 / crop.width, 390 / crop.height)
        labels, lanes = lane_labels(system["notes"], scale, lambda s: pdfmetrics.stringWidth(s, "Helvetica-Bold", 7.5), 2)
        image_height = crop.height * scale
        block_height = image_height + 18 * lanes + 26
        if block_height > 495:
            raise ValueError("A score row is too dense for the PDF; split the source system or revise layout")
        if top - block_height < 35 and on_page:
            footer()
            pdf.showPage()
            page_number += 1
            top, on_page = 535, False
            heading()
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(.35, .40, .46)
        pdf.drawString(30, top, f"Source p. {page} / System {system['system']} / {len(system['notes'])} noteheads")
        bottom = top - 6 - image_height
        pdf.drawImage(ImageReader(crop), 30, bottom, width=crop.width * scale, height=image_height)
        for note, lane in labels:
            x, yy = 30 + (note["x"] - x0) * scale, bottom - 9 - lane * 18
            pdf.setStrokeColorRGB(.68, .76, .82)
            pdf.setLineWidth(.3)
            pdf.line(x, bottom, x, yy + 7)
            pdf.setFillColorRGB(0, .29, .61)
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawCentredString(x, yy, note["display_pitch"])
            pdf.setFillColorRGB(.70, .30, .02)
            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(x, yy - 8, str(note["position"]) if note["position"] else "?")
        layout.append({"output_page": page_number, "source_page": page, "system": system["system"],
                       "crop": [x0, y0, crop.width, crop.height], "label_lanes": lanes})
        top -= block_height
        on_page = True
        webrows.append(html_row(page, system, crop, x0, y0))
    footer()
    pdf.save()
    (out / "pdf-layout.json").write_text(json.dumps(layout, indent=2) + "\n")

    notes = [n for systems in data["pages"].values() for system in systems for n in system["notes"]]
    for filename, rows, fields in (
        ("notes.csv", notes, ["note_id", "page", "system", "id", "pitch", "display_pitch", "midi", "position", "movement", "bar", "onset_ticks", "duration_ticks", "duration_quarters", "tie_to_next", "x", "y", "review_status", "timing_status", "audio_time_seconds"]),
        ("timeline.csv", data["timing"]["events"], ["kind", "note_id", "movement", "page", "system", "bar", "group", "onset_ticks", "duration_ticks", "rest_bars", "pitch", "midi", "tie_to_next", "tie_from_previous"]),
    ):
        with (out / filename).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    # Prevent project text from escaping inline script context (including </script>).
    safe_data = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    assets = Path(__file__).parent
    script = (assets / "player.js").read_text().replace("__DATA__", safe_data)
    values = {"TITLE": html.escape(project["title"]), "PART": html.escape(project["part"]),
              "STYLE": (assets / "player.css").read_text(), "ROWS": "".join(webrows), "SCRIPT": script,
              "NOTES": str(len(notes)), "REVIEW": html.escape(data["audit"]["review_status"]),
              "ISSUES": "".join("<li>" + html.escape(json.dumps(i, ensure_ascii=False)) + "</li>" for i in data["audit"]["issues"]),
              "MOVEMENTS": "".join(f'<option value="{m["id"]}">{html.escape(m["label"])}</option>' for m in project["movements"])}
    template = (assets / "player.html").read_text()
    # One substitution pass: user text containing a template token is literal.
    import re
    rendered = re.sub(r"__([A-Z]+)__", lambda m: values[m[1]], template)
    (out / "reading.html").write_text(rendered, encoding="utf-8")
