"""Validate Obsidian brain notes and links."""

import datetime
import os
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
ALLOWED_TYPES = frozenset(
    {"inbox", "project", "area", "resource", "archive", "ai-session", "review"}
)
ALLOWED_STATUSES = frozenset({"raw", "distilled"})
REQUIRED_KEYS = ("title", "type", "created", "tags", "requirements", "sources", "status")


def parse_frontmatter(content: str) -> tuple[dict[str, str] | None, str | None]:
    """Parse YAML frontmatter delimited by --- lines."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing frontmatter"
    frontmatter_lines: list[str] = []
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
        frontmatter_lines.append(lines[i])
    if end_idx == -1:
        return None, "unterminated frontmatter"

    data: dict[str, str] = {}
    for line in frontmatter_lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        if ":" not in line:
            return None, f"invalid frontmatter line: {line}"
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip()
    return data, None


def extract_wikilinks(content: str) -> list[str]:
    """Extract wikilink targets outside of fenced code blocks."""
    links: list[str] = []
    in_code_block = False
    for line in content.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for match in WIKILINK_RE.finditer(line):
            target = match.group(1).strip()
            links.append(target)
    return links


def is_note_file(p: Path) -> bool:
    """Determine whether p is a note file subject to frontmatter rules."""
    norm = p.as_posix()
    if norm in ("brain/index.md", "brain/log.md"):
        return False
    if norm.startswith("brain/templates/"):
        return False
    return True


def check_stems(all_md_files: list[Path]) -> list[str]:
    """Check that stems of all *.md files under brain/ are unique."""
    stem_to_paths: dict[str, list[Path]] = {}
    for p in all_md_files:
        stem_to_paths.setdefault(p.stem, []).append(p)

    errors: list[str] = []
    for stem, paths in sorted(stem_to_paths.items()):
        if len(paths) > 1:
            err = f"ERROR: {paths[0]}: duplicate stem '{stem}' also in {paths[1]}"
            errors.append(err)
            print(err)
    return errors


def _validate_note_fields(p: Path, data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"ERROR: {p}: missing key '{key}'")

    if "type" in data and data["type"] not in ALLOWED_TYPES:
        type_val = data["type"]
        errors.append(f"ERROR: {p}: invalid type '{type_val}'")

    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        status_val = data["status"]
        errors.append(f"ERROR: {p}: invalid status '{status_val}'")

    if "created" in data:
        created_val = data["created"]
        if not DATE_RE.match(created_val):
            errors.append(f"ERROR: {p}: created '{created_val}' does not match YYYY-MM-DD")
        else:
            try:
                datetime.date.fromisoformat(created_val)
            except ValueError:
                errors.append(
                    f"ERROR: {p}: created date '{created_val}' is not a valid calendar date"
                )

    if "title" in data and data["title"] != p.stem:
        title_val = data["title"]
        errors.append(f"ERROR: {p}: title '{title_val}' does not match file stem '{p.stem}'")

    return errors


def validate_note_file(p: Path) -> list[str]:
    """Validate frontmatter and fields of a note file."""
    try:
        content = p.read_text(encoding="utf-8")
    except Exception as exc:
        err = f"ERROR: {p}: failed to read: {exc}"
        print(err)
        return [err]

    data, err_msg = parse_frontmatter(content)
    if err_msg or data is None:
        err = f"ERROR: {p}: {err_msg}"
        print(err)
        return [err]

    errors = _validate_note_fields(p, data)
    for err in errors:
        print(err)
    return errors


def check_wikilinks(all_md_files: list[Path], existing_stems: set[str]) -> list[str]:
    """Check that all wikilinks point to existing stems."""
    errors: list[str] = []
    for p in all_md_files:
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as exc:
            err = f"ERROR: {p}: failed to read: {exc}"
            errors.append(err)
            print(err)
            continue

        wikilinks = extract_wikilinks(content)
        for target in wikilinks:
            if target not in existing_stems:
                err = f"ERROR: {p}: broken wikilink [[{target}]]"
                errors.append(err)
                print(err)
    return errors


def main() -> None:
    """Main entry point for brain validation."""
    brain_dir = Path("brain")
    if not brain_dir.is_dir():
        print("ERROR: brain/ directory missing")
        sys.exit(1)

    errors: list[str] = []

    all_md_files: list[Path] = []
    for root, dirs, files in os.walk(brain_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith(".md"):
                all_md_files.append(Path(root) / file)

    all_md_files.sort(key=lambda p: p.as_posix())

    errors.extend(check_stems(all_md_files))
    existing_stems = {p.stem for p in all_md_files}

    note_files = [p for p in all_md_files if is_note_file(p)]
    for p in note_files:
        errors.extend(validate_note_file(p))

    errors.extend(check_wikilinks(all_md_files, existing_stems))

    if errors:
        print(f"validate_brain: FAILED ({len(errors)} errors)")
        sys.exit(1)

    print(f"validate_brain: OK ({len(note_files)} notes checked)")
    sys.exit(0)


if __name__ == "__main__":
    main()
