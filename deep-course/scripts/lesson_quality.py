"""Deterministic, content-first lesson quality checks."""
from html.parser import HTMLParser
from pathlib import Path
import math
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
    """Collect instructional prose while excluding interface and support sections."""

    _IGNORED_TAGS = {"script", "style", "nav", "form", "label", "button", "input", "select", "option", "textarea"}
    _SECTION_TAGS = {"section", "aside"}
    _NONINSTRUCTIONAL_CONTAINER = re.compile(r"(?:^|[-_\s])(answer(?:s|[-_\s]*key)?|sources?|references?)(?:$|[-_\s])", re.IGNORECASE)
    _NONINSTRUCTIONAL_HEADING = re.compile(r"^\s*(?:answer(?:s|\s+key)?|sources?|references?)\b", re.IGNORECASE)

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._sections: list[dict[str, object]] = []
        self._heading_sections: list[dict[str, object]] = []
        self.parts: list[str] = []

    @classmethod
    def _is_named_noninstructional_container(cls, attrs: list[tuple[str, str | None]]) -> bool:
        return any(
            name.lower() in {"class", "id"}
            and value is not None
            and cls._NONINSTRUCTIONAL_CONTAINER.search(value) is not None
            for name, value in attrs
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        is_named_noninstructional = self._is_named_noninstructional_container(attrs)
        if tag in self._SECTION_TAGS or is_named_noninstructional:
            self._sections.append({
                "tag": tag,
                "parts": [],
                "headings": [],
                "is_named_noninstructional": is_named_noninstructional,
            })
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._sections:
            self._heading_sections.append(self._sections[-1])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return None

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_sections:
            self._heading_sections.pop()
        if self._sections and self._sections[-1]["tag"] == tag:
            section = self._sections.pop()
            headings = section["headings"]
            is_named_noninstructional = bool(section["is_named_noninstructional"])
            if not is_named_noninstructional and not any(self._NONINSTRUCTIONAL_HEADING.search(heading) for heading in headings):
                if self._sections:
                    self._sections[-1]["parts"].extend(section["parts"])
                else:
                    self.parts.extend(section["parts"])

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._sections:
            self._sections[-1]["parts"].append(data)
        else:
            self.parts.append(data)
        if self._heading_sections:
            self._heading_sections[-1]["headings"].append(data)

def _error(code: str, message: str, *, path: str | None = None, field: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    if field is not None:
        item["field"] = field
    return item


def _strip_fenced_code_blocks(text: str) -> str:
    """Remove CommonMark fenced code, including unclosed fences through EOF."""
    retained: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        stripped_line = line.rstrip("\r\n")
        if fence_character is None:
            opener = re.match(r"^ {0,3}(`{3,}|~{3,})[^\r\n]*$", stripped_line)
            if opener:
                marker = opener.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
            else:
                retained.append(line)
        elif re.fullmatch(rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*", stripped_line):
            fence_character = None
            fence_length = 0
    return "".join(retained)


def _strip_markdown_noninstructional(text: str) -> str:
    text = _strip_fenced_code_blocks(text)
    text = re.sub(r"(?m)^(?: {4}|\t).*(?:\n(?: {4}|\t).*)*", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(?:answer(?:s| key)?|sources?|references?)\b.*$(?:\n(?!\s{0,3}#{1,6}\s).*)*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?im)^\s*(?:(?:navigation|previous|next|back|continue)(?:[\s|·•]+(?:previous|next|back|continue))*)\s*$", "", text)
    return re.sub(r"[`*_~>#]", "", text)


def _read_text(path: Path, relative_path: str) -> tuple[str | None, dict | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, _error("missing_artifact", "Required lesson artifact is missing.", path=relative_path)
    except (OSError, UnicodeError):
        return None, _error("unreadable_artifact", "Required lesson artifact could not be read as UTF-8 text.", path=relative_path)
    if any((ord(character) < 32 and character not in "\t\n\r") or 127 <= ord(character) <= 159 for character in text):
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
    if (
        isinstance(planned_minutes, bool)
        or not isinstance(planned_minutes, (int, float))
        or not math.isfinite(planned_minutes)
    ):
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

    depth_band = _depth_band(manifest.get("planned_minutes"))
    if depth_band is None:
        report["errors"].append(_error(
            "invalid_time_evidence",
            "planned_minutes must be a finite number in a supported lesson-duration band.",
            field="planned_minutes",
        ))
    elif report["metrics"]["markdown_reading_units"] < DEPTH_LIMITS[depth_band]["floor"]:
        report["errors"].append(_error(
            "insufficient_reading_depth",
            f"{depth_band.title()}-depth lessons need at least {DEPTH_LIMITS[depth_band]['floor']:,} Markdown reading units.",
            path=f"{directory}/lesson.md",
            field="planned_minutes",
        ))
    report["valid"] = not report["errors"]
    return report
