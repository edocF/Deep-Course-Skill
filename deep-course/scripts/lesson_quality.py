"""Deterministic, content-first lesson quality checks."""
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Mapping


DEPTH_LIMITS = {
    "light": {"minutes": (12, 20), "floor": 600, "target": (900, 1800)},
    "normal": {"minutes": (30, 45), "floor": 1800, "target": (2500, 5000)},
    "deep": {"minutes": (60, 90), "floor": 3500, "target": (5000, 9000)},
}


def reading_units(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_words = len(re.findall(r"\b[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*\b", text))
    return cjk + 2 * latin_words


class _VisibleHTMLText(HTMLParser):
    """Collect learner-facing prose while excluding interface and executable text."""

    _IGNORED_TAGS = {"script", "style", "nav", "form", "label", "button", "input", "select", "option", "textarea"}

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return None

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _error(code: str, message: str, *, path: str | None = None, field: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    if field is not None:
        item["field"] = field
    return item


def _strip_markdown_noninstructional(text: str) -> str:
    text = re.sub(r"(?ms)^\s*```.*?^\s*```\s*$", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(?:answer(?:s| key)?|sources?|references?)\b.*$(?:\n(?!\s{0,3}#{1,6}\s).*)*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?im)^\s*(?:navigation|previous|next|back|continue)\s*$", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[`*_~>#]", "", text)


def _read_text(path: Path, relative_path: str) -> tuple[str | None, dict | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, _error("missing_artifact", "Required lesson artifact is missing.", path=relative_path)
    except (OSError, UnicodeError):
        return None, _error("unreadable_artifact", "Required lesson artifact could not be read as UTF-8 text.", path=relative_path)
    if "\x00" in text:
        return None, _error("non_text_artifact", "Required lesson artifact must contain text, not binary data.", path=relative_path)
    return text, None


def _contained_lesson_directory(root: Path, manifest: Mapping[str, object]) -> tuple[Path | None, str | None, dict | None]:
    directory = manifest.get("lesson_directory")
    if not isinstance(directory, str) or not directory:
        return None, None, _error("invalid_artifact_path", "lesson_directory must be a non-empty relative path.", field="lesson_directory")
    candidate = Path(directory)
    if candidate.is_absolute():
        return None, None, _error("invalid_artifact_path", "lesson_directory must stay inside the course root.", field="lesson_directory")
    try:
        resolved_root = root.resolve()
        resolved_lesson = (resolved_root / candidate).resolve()
        resolved_lesson.relative_to(resolved_root)
    except (OSError, ValueError):
        return None, None, _error("invalid_artifact_path", "lesson_directory must stay inside the course root.", field="lesson_directory")
    return resolved_lesson, candidate.as_posix(), None


def _depth_band(planned_minutes: object) -> str | None:
    if isinstance(planned_minutes, bool) or not isinstance(planned_minutes, (int, float)):
        return None
    for name, limit in DEPTH_LIMITS.items():
        low, high = limit["minutes"]
        if low <= planned_minutes <= high:
            return name
    return None


def audit_lesson(root: Path, manifest: Mapping[str, object]) -> dict:
    """Measure a lesson's readable Markdown and HTML, reporting errors structurally."""
    report = {"valid": True, "errors": [], "warnings": [], "metrics": {
        "markdown_reading_units": 0,
        "html_reading_units": 0,
    }}
    if not isinstance(manifest, Mapping):
        report["errors"].append(_error("invalid_manifest", "Lesson manifest must be a mapping."))
        report["valid"] = False
        return report

    try:
        course_root = Path(root)
    except TypeError:
        report["errors"].append(_error("invalid_artifact_path", "Course root is not a valid path."))
        report["valid"] = False
        return report
    lesson_dir, directory, directory_error = _contained_lesson_directory(course_root, manifest)
    if directory_error:
        report["errors"].append(directory_error)
        report["valid"] = False
        return report

    markdown, markdown_error = _read_text(lesson_dir / "lesson.md", f"{directory}/lesson.md")
    html, html_error = _read_text(lesson_dir / "lesson.html", f"{directory}/lesson.html")
    for error in (markdown_error, html_error):
        if error:
            report["errors"].append(error)
    if markdown is not None:
        report["metrics"]["markdown_reading_units"] = reading_units(_strip_markdown_noninstructional(markdown))
    if html is not None:
        parser = _VisibleHTMLText()
        try:
            parser.feed(html)
            parser.close()
        except (ValueError, OSError):
            report["errors"].append(_error("unreadable_artifact", "Required lesson HTML could not be parsed.", path=f"{directory}/lesson.html"))
        else:
            report["metrics"]["html_reading_units"] = reading_units(_strip_markdown_noninstructional(" ".join(parser.parts)))

    if _depth_band(manifest.get("planned_minutes")) == "normal" and report["metrics"]["markdown_reading_units"] < DEPTH_LIMITS["normal"]["floor"]:
        report["errors"].append(_error(
            "insufficient_reading_depth",
            "Normal-depth lessons need at least 1,800 Markdown reading units.",
            path=f"{directory}/lesson.md",
            field="planned_minutes",
        ))
    report["valid"] = not report["errors"]
    return report
