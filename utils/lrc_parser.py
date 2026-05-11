from __future__ import annotations
import re
from core.models import LyricLine

_LINE_RE = re.compile(r"\[(\d{2}):(\d{2,3})\.(\d{2,3})\](.*)")


def _parse_ms(minutes: str, seconds: str, centis: str) -> int:
    # Normalize centiseconds/milliseconds field to ms
    frac = centis.ljust(3, "0")[:3]
    return int(minutes) * 60_000 + int(seconds) * 1_000 + int(frac)


def parse_lrc(lrc_text: str) -> list[LyricLine]:
    if not lrc_text.strip():
        return []

    parsed: list[tuple[int, str]] = []
    for raw_line in lrc_text.splitlines():
        m = _LINE_RE.match(raw_line.strip())
        if m:
            start_ms = _parse_ms(m.group(1), m.group(2), m.group(3))
            text = m.group(4).strip()
            parsed.append((start_ms, text))

    if not parsed:
        return []

    lines: list[LyricLine] = []
    for i, (start_ms, text) in enumerate(parsed):
        end_ms = parsed[i + 1][0] if i + 1 < len(parsed) else start_ms + 5_000
        lines.append(LyricLine(start_ms=start_ms, end_ms=end_ms, text=text))

    return lines
