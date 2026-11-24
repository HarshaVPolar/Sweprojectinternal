"""Validate skill definitions in skills/ directory."""

import os
import re
import sys
from pathlib import Path

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


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


def _validate_skill_name(skill_md: Path, dir_name: str, name_val: str) -> list[str]:
    errors: list[str] = []
    if name_val != dir_name:
        errors.append(f"ERROR: {skill_md}: name '{name_val}' does not match directory '{dir_name}'")
    elif not SKILL_NAME_RE.match(name_val):
        errors.append(f"ERROR: {skill_md}: name '{name_val}' does not match regex")
    elif len(name_val) > 64:
        errors.append(f"ERROR: {skill_md}: name '{name_val}' exceeds 64 characters")
    return errors


def _validate_skill_description(skill_md: Path, desc_val: str) -> list[str]:
    errors: list[str] = []
    if not desc_val:
        errors.append(f"ERROR: {skill_md}: description is empty")
    elif len(desc_val) > 1024:
        errors.append(f"ERROR: {skill_md}: description exceeds 1024 characters")
    return errors


def validate_skill_dir(d: Path, strict_skills: bool) -> tuple[list[str], int]:
    """Validate a single skill directory."""
    skill_md = d / "SKILL.md"
    if not skill_md.is_file():
        if strict_skills:
            err = f"ERROR: skills/{d.name}/SKILL.md: skills/{d.name}/SKILL.md missing"
            print(err)
            return [err], 0
        print(f"WARNING: skills/{d.name}/SKILL.md missing")
        return [], 1

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as exc:
        err = f"ERROR: {skill_md}: failed to read: {exc}"
        print(err)
        return [err], 0

    data, err_msg = parse_frontmatter(content)
    if err_msg or data is None:
        err = f"ERROR: {skill_md}: {err_msg}"
        print(err)
        return [err], 0

    errors: list[str] = []
    if "name" not in data:
        errors.append(f"ERROR: {skill_md}: missing key: name")
    else:
        errors.extend(_validate_skill_name(skill_md, d.name, data["name"]))

    if "description" not in data:
        errors.append(f"ERROR: {skill_md}: missing key: description")
    else:
        errors.extend(_validate_skill_description(skill_md, data["description"]))

    for err in errors:
        print(err)

    return errors, 0


def main() -> None:
    """Main entry point for skills validation."""
    skills_dir = Path("skills")
    if not skills_dir.is_dir():
        print("ERROR: skills/ directory missing")
        sys.exit(1)

    strict_skills = os.environ.get("STRICT_SKILLS") == "1"
    subdirs = sorted([d for d in skills_dir.iterdir() if d.is_dir()], key=lambda p: p.name)

    total_warnings = 0
    all_errors: list[str] = []

    for d in subdirs:
        errs, warns = validate_skill_dir(d, strict_skills)
        all_errors.extend(errs)
        total_warnings += warns

    if all_errors:
        print(f"validate_skills: FAILED ({len(all_errors)} errors)")
        sys.exit(1)

    print(f"validate_skills: OK ({len(subdirs)} skills checked, {total_warnings} warnings)")
    sys.exit(0)


if __name__ == "__main__":
    main()
