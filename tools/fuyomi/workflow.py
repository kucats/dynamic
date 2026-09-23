"""Hash-bound local workspaces and restartable stages for fuyomi."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile

from . import PIPELINE_VERSION, SCHEMA_VERSION
from .score import CLEFS, apply_corrections, attach_rhythm, playback_events, read_omr


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError(f"Refusing symlink output: {path.name}")
    temporary.write_bytes(json_bytes(value))
    temporary.replace(path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return value


def local_path(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts or path.resolve().is_relative_to(root.resolve()) is False:
        raise ValueError(f"Workspace path must be relative and contained: {relative}")
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ValueError(f"Workspace symlinks are not supported: {relative}")
    return path


def parse_pages(text: str) -> list[int]:
    pages = []
    for item in text.split(","):
        values = item.strip().split("-")
        if len(values) == 1:
            pages.append(int(values[0]))
        elif len(values) == 2:
            a, b = map(int, values)
            if b < a:
                raise ValueError("Descending page range")
            pages.extend(range(a, b + 1))
        else:
            raise ValueError("Use page ranges such as 2-5,8")
    if not pages or min(pages) < 1 or len(set(pages)) != len(pages) or pages != sorted(pages):
        raise ValueError("Pages must be positive, unique and ascending")
    return pages


def dependency_versions() -> dict:
    result = {}
    for name in ("Pillow", "pypdf", "reportlab"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError("Install fuyomi dependencies: pip install Pillow pypdf reportlab") from exc
    return result


def engine_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.iterdir()):
        if path.suffix in (".py", ".js", ".css", ".html"):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def init_workspace(source: Path, root: Path, pages: list[int], *, title: str, part: str,
                   clef: str, fifths: int, meter: list[int], image_mode: str = "render",
                   dpi: int = 300) -> dict:
    dependency_versions()
    from PIL import Image
    from pypdf import PdfReader

    started, clock = utc_now(), time.monotonic()
    if root.exists():
        raise ValueError("Workspace already exists; select a new directory")
    if clef not in CLEFS or not -7 <= fifths <= 7 or not 72 <= dpi <= 600:
        raise ValueError("Invalid clef, key signature or render DPI")
    if len(meter) != 2 or min(meter) <= 0:
        raise ValueError("Meter must contain two positive integers")
    source_hash = sha256(source)
    reader = PdfReader(source)
    if max(pages) > len(reader.pages):
        raise ValueError("Selected page exceeds source PDF length")
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fuyomi-init-", dir=root.parent) as temporary:
        stage = Path(temporary) / "workspace"
        (stage / "images").mkdir(parents=True)
        images = {}
        for page in pages:
            relative = f"images/page-{page:04}.png"
            image_path = stage / relative
            if image_mode == "embedded":
                embedded = list(reader.pages[page - 1].images)
                if len(embedded) != 1:
                    raise ValueError("Embedded mode requires exactly one full-page raster; use render otherwise")
                embedded[0].image.convert("RGB").save(image_path)
            else:
                executable = shutil.which("pdftoppm")
                if not executable:
                    raise RuntimeError("Install Poppler (pdftoppm), or explicitly choose --image-mode embedded")
                subprocess.run([executable, "-f", str(page), "-l", str(page), "-singlefile", "-r", str(dpi),
                                "-png", str(source.resolve()), str(image_path.with_suffix(""))],
                               check=True, capture_output=True, timeout=180)
            with Image.open(image_path) as image:
                width, height = image.size
            images[str(page)] = {"path": relative, "sha256": sha256(image_path), "width": width, "height": height}
        if sha256(source) != source_hash:
            raise ValueError("Source PDF changed during initialization")
        project = {"schema_version": SCHEMA_VERSION, "workflow": "fuyomi", "title": title, "part": part,
                   "source": {"filename": source.name, "sha256": source_hash, "page_count": len(reader.pages),
                              "image_mode": image_mode, "dpi": dpi if image_mode == "render" else None,
                              "images": images},
                   "default_clef": clef, "default_fifths": fifths,
                   "movements": [{"id": 1, "label": "Movement 1", "pages": pages, "meter": meter, "practice_bpm": 120}],
                   "position_convention": "Bb open-tube basic positions, MIDI 40-70; no valves or intonation offsets",
                   "recording_alignment_status": "not_aligned", "review_issues": [],
                   "layout": {"pages": {}}, "process_notes": []}
        write_json(stage / "project.json", project)
        write_json(stage / "init-receipt.json", {"started_at": started, "finished_at": utc_now(),
                                                "elapsed_seconds": round(time.monotonic() - clock, 3),
                                                "source_sha256": source_hash, "pipeline_version": PIPELINE_VERSION})
        stage.rename(root)
    return {"status": "initialized", "workspace": str(root), "pages": pages}


def load_project(root: Path) -> dict:
    project = read_json(local_path(root, "project.json"))
    if project.get("schema_version") != SCHEMA_VERSION or project.get("workflow") != "fuyomi":
        raise ValueError("Unsupported fuyomi project schema")
    if project.get("recording_alignment_status") != "not_aligned":
        raise ValueError("Recording alignment is not implemented; do not claim synchronized recording playback")
    for image in project["source"]["images"].values():
        if sha256(local_path(root, image["path"])) != image["sha256"]:
            raise ValueError("Source image checksum mismatch")
    return project


def import_omr(root: Path, sources: dict[int, Path], engine_version: str) -> dict:
    project = load_project(root)
    if any((root / name).exists() for name in ("recognition.json", "candidates.json", "corrections.json", "rhythm.json")):
        raise ValueError("Recognition/review already exists; use a new workspace to re-recognize without discarding review")
    if set(map(str, sources)) != set(project["source"]["images"]):
        raise ValueError("Supply one PAGE=PATH .omr for every selected page")
    started, clock = utc_now(), time.monotonic()
    candidates = {"schema_version": SCHEMA_VERSION, "default_clef": project["default_clef"], "pages": {}}
    omr_manifest = {}
    with tempfile.TemporaryDirectory(prefix=".fuyomi-import-", dir=root) as temporary:
        stage = Path(temporary)
        for page, path in sorted(sources.items()):
            candidates["pages"][str(page)] = read_omr(path, default_clef=project["default_clef"], default_fifths=project["default_fifths"])
            relative = f"recognition/page-{page:04}.omr"
            (stage / "recognition").mkdir(exist_ok=True)
            shutil.copyfile(path, stage / relative)
            omr_manifest[str(page)] = {"path": relative, "sha256": sha256(stage / relative)}
        write_json(stage / "candidates.json", candidates)
        binding = {"source_sha256": project["source"]["sha256"], "candidates_sha256": sha256(stage / "candidates.json")}
        corrections = {"schema_version": SCHEMA_VERSION, "binding": binding, "pages": {}}
        rhythm = {"schema_version": SCHEMA_VERSION, "binding": binding, "pages": {}, "repeat_regions": [], "performance_notes": []}
        for page, systems in candidates["pages"].items():
            corrections["pages"][page], rhythm["pages"][page] = {}, {}
            for system in systems:
                sid = str(system["system"])
                review = {"status": "unreviewed", "by": "", "note": ""}
                corrections["pages"][page][sid] = {"review": review, "remove": [], "replace": {}, "add": [], "reason": ""}
                rhythm["pages"][page][sid] = {"review": review, "tokens": ""}
        write_json(stage / "corrections.json", corrections)
        write_json(stage / "rhythm.json", rhythm)
        write_json(stage / "recognition.json", {"schema_version": SCHEMA_VERSION, "binding": binding,
                                                "engine": "Audiveris", "declared_engine_version": engine_version,
                                                "parser_version": PIPELINE_VERSION,
                                                "parser_defaults": [project["default_clef"], project["default_fifths"]],
                                                "files": omr_manifest, "started_at": started,
                                                "elapsed_seconds": round(time.monotonic() - clock, 3)})
        for path in stage.iterdir():
            path.rename(local_path(root, path.name))
    return {"status": "review_required", "systems": sum(map(len, candidates["pages"].values())),
            "candidates": sum(len(s["notes"]) for ss in candidates["pages"].values() for s in ss),
            "edit": ["project.json", "corrections.json", "rhythm.json"]}


def recognize(root: Path, executable: Path, engine_version: str, timeout: int = 600) -> dict:
    project = load_project(root)
    if (root / "recognition.json").exists():
        raise ValueError("Recognition already imported; rebuild uses saved results without re-running OMR")
    executable = executable.resolve()
    identity = {"executable_sha256": sha256(executable), "declared_version": engine_version,
                "arguments": ["-batch", "-transcribe", "-save"], "pipeline_version": PIPELINE_VERSION}
    sources = {}
    for page, image in project["source"]["images"].items():
        key = hashlib.sha256(json_bytes({**identity, "image_sha256": image["sha256"]})).hexdigest()
        cache = local_path(root, f"omr-cache/{page}-{key}")
        receipt = cache / "receipt.json"
        output = cache / f"page-{int(page):04}.omr"
        if receipt.exists():
            previous = read_json(receipt)
            if not output.exists() or sha256(output) != previous["omr_sha256"]:
                raise ValueError("Recognition cache checksum mismatch; remove the corrupt cache directory explicitly")
        else:
            cache.mkdir(parents=True, exist_ok=True)
            started, clock = utc_now(), time.monotonic()
            command = [str(executable), *identity["arguments"], "-output", str(cache.resolve()), "--", str(local_path(root, image["path"]).resolve())]
            with (cache / "audiveris.log").open("wb") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
            if result.returncode != 0 or not output.exists():
                raise RuntimeError(f"Audiveris failed for page {page}; inspect {cache / 'audiveris.log'}")
            read_omr(output, default_clef=project["default_clef"], default_fifths=project["default_fifths"])
            write_json(receipt, {**identity, "image_sha256": image["sha256"], "omr_sha256": sha256(output),
                                 "started_at": started, "elapsed_seconds": round(time.monotonic() - clock, 3)})
        sources[int(page)] = output
    return import_omr(root, sources, engine_version)


def load_inputs(root: Path) -> tuple[dict, dict, dict, dict, dict]:
    project = load_project(root)
    candidates, corrections, rhythm, recognition = [read_json(local_path(root, name + ".json"))
                                                   for name in ("candidates", "corrections", "rhythm", "recognition")]
    binding = {"source_sha256": project["source"]["sha256"], "candidates_sha256": sha256(root / "candidates.json")}
    for document in (candidates, corrections, rhythm, recognition):
        if document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported input schema version")
    for document in (corrections, rhythm, recognition):
        if document["binding"] != binding:
            raise ValueError("Review binding is stale: original source or recognition candidates changed")
    if recognition["parser_defaults"] != [project["default_clef"], project["default_fifths"]]:
        raise ValueError("Clef/key defaults changed after recognition; correct per-system pitches or re-import in a new workspace")
    for item in recognition["files"].values():
        if sha256(local_path(root, item["path"])) != item["sha256"]:
            raise ValueError("Saved recognition checksum mismatch")
    hashes = {name: sha256(local_path(root, name)) for name in
              ("project.json", "candidates.json", "corrections.json", "rhythm.json", "recognition.json")}
    return project, candidates, corrections, rhythm, hashes


def compile_score(root: Path) -> tuple[dict, dict, dict]:
    project, candidates, corrections, rhythm, hashes = load_inputs(root)
    pages, issues = apply_corrections(candidates, corrections)
    timing, rhythm_issues = attach_rhythm(pages, rhythm, project["movements"])
    issues.extend(rhythm_issues)
    issues.extend(project.get("review_issues", []))
    for page, systems in pages.items():
        image = project["source"]["images"][page]
        for system in systems:
            for note in system["notes"]:
                if not (0 <= note["x"] < image["width"] and 0 <= note["y"] < image["height"]):
                    raise ValueError(f"Note coordinates outside source image: {note['note_id']}")
    notes = [n for ss in pages.values() for s in ss for n in s["notes"]]
    status = "needs_review" if issues else "source_checked"
    audit = {"schema_version": SCHEMA_VERSION, "structural_checks": "passed", "review_status": status,
             "note_count": len(notes), "rest_count": sum(e["kind"] == "rest" for e in timing["events"]),
             "tie_count": sum(bool(e.get("tie_to_next")) for e in timing["events"]),
             "removed_candidates": sum(len(s["notes"]) for ss in candidates["pages"].values() for s in ss)
                                   - sum(n.get("raw_id") is not None for n in notes),
             "added_notes": sum(bool(n.get("manual_addition")) for n in notes),
             "pitch_corrections": sum(n.get("raw_pitch") is not None and n["raw_pitch"] != n["pitch"] for n in notes),
             "issues": issues, "input_hashes": hashes,
             "recording_alignment_status": "not_aligned", "human_listening_test": "not_recorded"}
    data = {"schema_version": SCHEMA_VERSION, "work": project["title"], "part": project["part"],
            "source_sha256": project["source"]["sha256"], "pages": pages, "timing": timing,
            "movements": project["movements"], "audit": audit,
            "playback": {str(m["id"]): {"once": playback_events(timing, m["id"], False),
                                         "repeats": playback_events(timing, m["id"], True)} for m in project["movements"]}}
    return data, audit, project


def verify_build(root: Path, relative: str, input_hashes: dict | None = None) -> dict:
    directory = local_path(root, relative)
    receipt = read_json(local_path(directory, "receipt.json"))
    if input_hashes is not None and receipt["input_hashes"] != input_hashes:
        raise ValueError("Build is stale: reviewed inputs changed")
    for name, expected in receipt["artifacts"].items():
        if sha256(local_path(directory, name)) != expected:
            raise ValueError(f"Build artifact checksum mismatch: {name}")
    return receipt


def build(root: Path, *, font: Path | None = None) -> dict:
    from .render import render_outputs

    started, clock = utc_now(), time.monotonic()
    data, audit, project = compile_score(root)
    versions = dependency_versions()
    fingerprint = {"input_hashes": audit["input_hashes"], "engine_sha256": engine_digest(),
                   "dependencies": versions, "font_sha256": sha256(font) if font else None}
    key = hashlib.sha256(json_bytes(fingerprint)).hexdigest()
    relative = f"builds/{key}"
    target = local_path(root, relative)
    if target.exists():
        verify_build(root, relative, audit["input_hashes"])
        write_json(local_path(root, "latest.json"), {"build": relative})
        return {"status": audit["review_status"], "cached": True, "output": str(target), "notes": audit["note_count"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fuyomi-build-", dir=target.parent) as temporary:
        stage = Path(temporary) / "output"
        stage.mkdir()
        render_outputs(root, stage, data, project, font)
        write_json(stage / "score.json", data)
        write_json(stage / "review-audit.json", audit)
        finished = utc_now()
        elapsed = round(time.monotonic() - clock, 3)
        initialized = read_json(root / "init-receipt.json")["started_at"]
        wall_elapsed = (datetime.fromisoformat(finished) - datetime.fromisoformat(initialized)).total_seconds()
        report = [f"# {project['title']} / {project['part']}", "", f"レビュー状態: {audit['review_status']}",
                  f"音符 {audit['note_count']} / 休符イベント {audit['rest_count']} / タイ {audit['tie_count']}", "",
                  f"生成処理: {elapsed:.3f} 秒。ワークスペース作成からの経過: {wall_elapsed / 60:.1f} 分。",
                  "後者は待機・編集時間を含む実時間で、作業者の実働時間ではありません。", "",
                  "原譜登録 → Audiveris候補 → 根拠付き音高補正 → 音価・休符・タイの転記 → 整合検証 → PDF・試聴ページを生成。",
                  f"候補除外 {audit['removed_candidates']} / 追加 {audit['added_notes']} / 音高変更 {audit['pitch_corrections']}。",
                  "中央のド=C4、内部Bは表示H、Bbはシ♭。B♭管の基本ポジション（替え指・バルブ・微調整は対象外）。",
                  "一定テンポの合成単音再生。強弱・アーティキュレーション・フェルマータ延長は未再現。録音・YouTubeとは未同期。",
                  "構造検証の合格は目視レビュー・実聴の合格ではありません。review-audit.jsonで残件を確認してください。", "",
                  "## 未解決のレビュー項目", "", *[f"- {json.dumps(i, ensure_ascii=False)}" for i in audit["issues"]],
                  "", "## 処理メモ", "", *[str(n) for n in project.get("process_notes", [])], "",
                  "## 再現", "", "`python -m tools.fuyomi fuyomi validate WORKSPACE`",
                  "`python -m tools.fuyomi fuyomi build WORKSPACE` （生成時と同じ --font を指定）", "",
                  f"Pipeline {PIPELINE_VERSION}; engine source SHA256 {fingerprint['engine_sha256']}",
                  f"Source PDF SHA256 {project['source']['sha256']}",
                  "入力・依存関係・フォント・出力のハッシュはreceipt.jsonに保存。原譜PDFは変更・同梱しません。", ""]
        (stage / "process-report.md").write_text("\n".join(report), encoding="utf-8")
        receipt = {**fingerprint, "schema_version": SCHEMA_VERSION, "pipeline_version": PIPELINE_VERSION,
                   "started_at": started, "finished_at": finished, "elapsed_seconds": elapsed,
                   "workspace_elapsed_seconds": round(wall_elapsed, 3),
                   "artifacts": {p.name: sha256(p) for p in sorted(stage.iterdir()) if p.is_file()}}
        write_json(stage / "receipt.json", receipt)
        stage.rename(target)
    write_json(local_path(root, "latest.json"), {"build": relative})
    return {"status": audit["review_status"], "cached": False, "output": str(target), "notes": audit["note_count"], "elapsed_seconds": elapsed}


def validate(root: Path, *, source: Path | None = None) -> dict:
    _, audit, project = compile_score(root)
    if source is not None and sha256(source) != project["source"]["sha256"]:
        raise ValueError("Original PDF checksum mismatch")
    audit["original_pdf_checked"] = source is not None
    if (root / "latest.json").exists():
        verify_build(root, read_json(root / "latest.json")["build"], audit["input_hashes"])
        audit["build_artifacts"] = "passed"
    return audit


def bundle(root: Path, output: Path) -> dict:
    _, audit, project = compile_score(root)
    latest = read_json(root / "latest.json")
    receipt = verify_build(root, latest["build"], audit["input_hashes"])
    if output.exists():
        raise ValueError("Bundle already exists; choose a new output path")
    files = {Path(n) for n in ("project.json", "init-receipt.json", "recognition.json", "candidates.json",
                              "corrections.json", "rhythm.json", "latest.json")}
    files.update(Path(i["path"]) for i in project["source"]["images"].values())
    files.update(Path(i["path"]) for i in read_json(root / "recognition.json")["files"].values())
    files.update(Path(latest["build"]) / n for n in ["receipt.json", *receipt["artifacts"]])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(files):
            archive.write(local_path(root, str(relative)), str(Path("fuyomi") / relative))
        archive.writestr("fuyomi/REBUILD.txt", "Install the vEdit version identified by builds/*/receipt.json.\n"
                         "Run: python -m tools.fuyomi fuyomi validate fuyomi\n"
                         "Run: python -m tools.fuyomi fuyomi build fuyomi [--font same-font.ttf]\n"
                         "Source images, saved OMR and reviewed inputs are included. The source PDF and font are not.\n")
    return {"status": "bundled", "path": str(output), "sha256": sha256(output)}
