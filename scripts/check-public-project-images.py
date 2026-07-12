#!/usr/bin/env python3
"""Check that public project cards contain distinct exterior views and plans."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


PROJECTS_ROOT = Path(__file__).resolve().parents[1] / "public/site-assets/projects"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_image(project_dir: Path, stem: str) -> Path | None:
    return next(
        (path for suffix in (".webp", ".png") if (path := project_dir / f"{stem}{suffix}").is_file()),
        None,
    )


def project_issues(project_dir: Path) -> list[str]:
    facade = find_image(project_dir, "facade")
    side = find_image(project_dir, "side")
    issues = []
    if facade is None:
        issues.append("нет фасада")
    if side is None:
        issues.append("нет второго ракурса")

    for stem in ("facade", "side"):
        if (project_dir / f"{stem}.webp").is_file() and (project_dir / f"{stem}.png").is_file():
            issues.append(f"рядом с {stem}.webp остался устаревший {stem}.png")
    if list(project_dir.glob("*.original.png")) or list(project_dir.glob("*.generated.png")):
        issues.append("в публичной папке остались резервные изображения")

    plans = sorted(project_dir.glob("plan*.png"))
    if not plans:
        issues.append("нет планировки")

    if facade is not None and side is not None and file_hash(facade) == file_hash(side):
        issues.append("фасад и второй ракурс являются одним файлом")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prefixes",
        nargs="*",
        help="Проверять только серии по префиксу каталога, например h1 fam.",
    )
    args = parser.parse_args()
    prefixes = tuple(prefix.lower() for prefix in args.prefixes)

    project_dirs = sorted(path for path in PROJECTS_ROOT.iterdir() if path.is_dir())
    if prefixes:
        project_dirs = [path for path in project_dirs if path.name.lower().startswith(prefixes)]

    failed = 0
    for project_dir in project_dirs:
        issues = project_issues(project_dir)
        if issues:
            failed += 1
            print(f"FAIL {project_dir.name}: {'; '.join(issues)}")
        else:
            print(f"OK   {project_dir.name}")

    print(f"\nПроверено: {len(project_dirs)}; требуют доработки: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
