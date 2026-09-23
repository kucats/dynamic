"""Shared, offline helpers for validating the static score-reading catalog."""

from __future__ import annotations

import hashlib
import json
import posixpath
from pathlib import Path
from typing import Any


SHA256_LENGTH = 64
ALLOWED_REVIEW_STATES = {"reviewed", "draft"}


def load_catalog(root: Path) -> dict[str, Any]:
    path = root / "public" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def repo_file(root: Path, relative: str) -> Path:
    """Resolve a repository-relative file while refusing traversal and escapes."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"invalid repository path: {relative!r}")
    path = Path(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"path must be clean and repository-relative: {relative!r}")
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative!r}") from exc
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_LENGTH:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def validate_catalog(root: Path) -> list[str]:
    """Return all structural, path, metadata, and hash problems found."""
    errors: list[str] = []
    try:
        catalog = load_catalog(root)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read public/catalog.json: {exc}"]
    if not isinstance(catalog, dict):
        return ["public/catalog.json must contain an object"]

    if catalog.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    items = catalog.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["items must be a non-empty list"]

    seen_ids: set[str] = set()
    seen_pages: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{prefix}.id is required")
        elif item_id in seen_ids:
            errors.append(f"duplicate item id: {item_id}")
        else:
            seen_ids.add(item_id)

        for field in ("composer", "work", "instrument", "summary"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} is required")
        if item.get("review_status") not in ALLOWED_REVIEW_STATES:
            errors.append(f"{prefix}.review_status must be reviewed or draft")
        limitations = item.get("limitations")
        if not isinstance(limitations, list) or not limitations or not all(
            isinstance(value, str) and value.strip() for value in limitations
        ):
            errors.append(f"{prefix}.limitations must contain at least one explanation")

        for field in ("html", "project_readme"):
            try:
                target = repo_file(root, item.get(field))
                if not target.is_file():
                    errors.append(f"{prefix}.{field} does not exist: {item.get(field)!r}")
            except ValueError as exc:
                errors.append(f"{prefix}.{field}: {exc}")

        html_path = item.get("html")
        if isinstance(html_path, str):
            if html_path in seen_pages:
                errors.append(f"duplicate HTML page path: {html_path}")
            seen_pages.add(html_path)

        sources = item.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{prefix}.sources must list source hashes and exclusions")
        else:
            for source_index, source in enumerate(sources):
                if not isinstance(source, dict):
                    errors.append(f"{prefix}.sources[{source_index}] must be an object")
                    continue
                if not source.get("label") or not is_sha256(source.get("sha256")):
                    errors.append(f"{prefix}.sources[{source_index}] needs a label and SHA-256")
                if source.get("included") is not False:
                    errors.append(f"{prefix}.sources[{source_index}] must state included: false")

        artifacts = item.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"{prefix}.artifacts must contain hashed files")
        else:
            for artifact_index, artifact in enumerate(artifacts):
                artifact_prefix = f"{prefix}.artifacts[{artifact_index}]"
                if not isinstance(artifact, dict):
                    errors.append(f"{artifact_prefix} must be an object")
                    continue
                relative = artifact.get("path")
                expected_hash = artifact.get("sha256")
                if not artifact.get("kind") or not is_sha256(expected_hash):
                    errors.append(f"{artifact_prefix} needs kind and SHA-256")
                try:
                    target = repo_file(root, relative)
                    if not target.is_file():
                        errors.append(f"{artifact_prefix} does not exist: {relative!r}")
                    elif is_sha256(expected_hash) and sha256_file(target) != expected_hash:
                        errors.append(f"{artifact_prefix} SHA-256 mismatch: {relative}")
                    if artifact.get("kind") == "PDF" and target.is_file():
                        if target.read_bytes()[:5] != b"%PDF-":
                            errors.append(f"{artifact_prefix} is not a PDF: {relative}")
                except ValueError as exc:
                    errors.append(f"{artifact_prefix}: {exc}")

        project_files = item.get("project_files")
        if not isinstance(project_files, list) or not project_files:
            errors.append(f"{prefix}.project_files must list reproduction inputs")
        else:
            for project_file in project_files:
                try:
                    target = repo_file(root, project_file)
                    if not target.is_file():
                        errors.append(f"{prefix}.project_files missing: {project_file!r}")
                except ValueError as exc:
                    errors.append(f"{prefix}.project_files: {exc}")

        if isinstance(html_path, str):
            try:
                page = repo_file(root, html_path)
                if page.is_file():
                    text = page.read_text(encoding="utf-8")
                    pdf_artifacts = [
                        artifact.get("path")
                        for artifact in artifacts or []
                        if isinstance(artifact, dict) and artifact.get("kind") == "PDF"
                    ]
                    if len(pdf_artifacts) != 1:
                        errors.append(f"{prefix} must have exactly one PDF artifact")
                    elif posixpath.relpath(pdf_artifacts[0], posixpath.dirname(html_path)) not in text:
                        errors.append(f"{prefix}.html does not link to its PDF artifact")
                    for html_artifact in [
                        artifact.get("path")
                        for artifact in artifacts or []
                        if isinstance(artifact, dict) and artifact.get("kind") == "HTML"
                        and isinstance(artifact.get("path"), str)
                    ]:
                        html_link = posixpath.relpath(html_artifact, posixpath.dirname(html_path))
                        if html_link not in text:
                            errors.append(f"{prefix}.html does not link to its interactive HTML artifact")
                    review_status = item.get("review_status")
                    if isinstance(review_status, str) and review_status.lower() not in text.lower():
                        errors.append(f"{prefix}.html does not display its review status")
                    if not all(limit.lower() in text.lower() for limit in limitations or []):
                        errors.append(f"{prefix}.html does not list all limitations")
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                errors.append(f"{prefix}.html could not be read: {exc}")

    # Ensure the generated index and composer/work pages reach every catalog item.
    index_relative = "public/index.html"
    try:
        index_file = repo_file(root, index_relative)
        if not index_file.is_file():
            errors.append("public/index.html is missing; run tools/build_catalog.py")
        else:
            index_text = index_file.read_text(encoding="utf-8")
            work_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                composer_key, work_key = item.get("composer_key"), item.get("work_key")
                if not isinstance(composer_key, str) or not isinstance(work_key, str):
                    errors.append("each item needs composer_key and work_key")
                    continue
                work_groups.setdefault((composer_key, work_key), []).append(item)
            for (composer_key, work_key), group in work_groups.items():
                work_relative = f"public/composers/{composer_key}/{work_key}/index.html"
                work_link = posixpath.relpath(work_relative, "public")
                if work_link not in index_text:
                    errors.append(f"public/index.html does not link to {work_relative}")
                try:
                    work_file = repo_file(root, work_relative)
                    if not work_file.is_file():
                        errors.append(f"work index is missing: {work_relative}")
                        continue
                    work_text = work_file.read_text(encoding="utf-8")
                    for item in group:
                        html_link = posixpath.relpath(item.get("html", ""), posixpath.dirname(work_relative))
                        if html_link not in work_text:
                            errors.append(f"{work_relative} does not link to {item.get('html')}")
                        pdfs = [
                            artifact.get("path")
                            for artifact in item.get("artifacts", [])
                            if isinstance(artifact, dict) and artifact.get("kind") == "PDF"
                        ]
                        if len(pdfs) == 1:
                            pdf_link = posixpath.relpath(pdfs[0], posixpath.dirname(work_relative))
                            if pdf_link not in work_text:
                                errors.append(f"{work_relative} does not link to {pdfs[0]}")
                        for interactive_html in [
                            artifact.get("path")
                            for artifact in item.get("artifacts", [])
                            if isinstance(artifact, dict) and artifact.get("kind") == "HTML"
                            and isinstance(artifact.get("path"), str)
                        ]:
                            interactive_link = posixpath.relpath(interactive_html, posixpath.dirname(work_relative))
                            if interactive_link not in work_text:
                                errors.append(f"{work_relative} does not link to {interactive_html}")
                except (ValueError, OSError, UnicodeDecodeError) as exc:
                    errors.append(f"could not validate {work_relative}: {exc}")
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        errors.append(f"could not validate public/index.html: {exc}")

    # Public artifacts must not accidentally contain raw scan or audio bundles.
    public_root = root / "public"
    prohibited_suffixes = {".omr", ".jpg", ".jpeg", ".png", ".wav", ".flac", ".mp3", ".mid"}
    if public_root.exists():
        for path in public_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in prohibited_suffixes:
                errors.append(f"prohibited source/media file under public/: {path.relative_to(root)}")

    # Guard against accidental publication of machine-specific paths.
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".html", ".md", ".json", ".py", ".csv", ".css"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        machine_path_markers = ("/" + "Users" + "/", "/" + "home" + "/")
        if any(marker in content for marker in machine_path_markers):
            errors.append(f"machine-specific absolute path found in {path.relative_to(root)}")

    return errors
