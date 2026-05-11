from utils.lrc_parser import parse_lrc

LRC_SAMPLE = """[00:12.34]First line
[00:16.00]Second line
[01:02.500]Third line
[99:99.999]Last line""".strip()


def test_parse_returns_lyric_lines():
    from core.models import LyricLine
    lines = parse_lrc(LRC_SAMPLE)
    assert len(lines) == 4
    assert all(isinstance(l, LyricLine) for l in lines)


def test_first_line_text():
    lines = parse_lrc(LRC_SAMPLE)
    assert lines[0].text == "First line"


def test_timestamp_conversion_ms():
    lines = parse_lrc(LRC_SAMPLE)
    # [00:12.34] = 12340ms
    assert lines[0].start_ms == 12340
    # [00:16.00] = 16000ms
    assert lines[1].start_ms == 16000


def test_end_ms_is_next_start():
    lines = parse_lrc(LRC_SAMPLE)
    assert lines[0].end_ms == lines[1].start_ms


def test_last_line_end_ms():
    lines = parse_lrc(LRC_SAMPLE)
    last = lines[-1]
    assert last.end_ms == last.start_ms + 5000


def test_empty_lrc():
    assert parse_lrc("") == []


def test_lines_without_timestamp_are_skipped():
    lrc = "[00:01.00]A line\nNo timestamp here\n[00:03.00]Another"
    lines = parse_lrc(lrc)
    assert len(lines) == 2


def test_words_list_is_empty_for_plain_lrc():
    lines = parse_lrc(LRC_SAMPLE)
    for line in lines:
        assert line.words == []
