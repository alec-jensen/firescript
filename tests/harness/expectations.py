"""EXPECT block (golden output) and //~ ERROR (diagnostic) expectation
parsing, matching, and in-place rewriting (spec sec.5.3, sec.5.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from harness.directives import DirectiveError

BLOCK_OPEN = "/* EXPECT"
BLOCK_CLOSE = "*/"
LINE_PREFIX = "// EXPECT:"


def normalize_output(s: str) -> str:
    """Same normalization the run kind applies to actual and expected output:
    CRLF/CR -> LF, strip trailing whitespace per line, single trailing
    newline."""
    unified = s.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n")).strip() + "\n"


@dataclass
class ExpectBlock:
    content_norm: str  # normalized expected content, e.g. "42\ndone\n"
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    form: str  # "block" or "line"


def _trailing_nonblank_range(lines: list[str]) -> tuple[int, int] | None:
    """Index range [start, end) of the trailing contiguous non-blank block,
    or None if the file ends with no content."""
    end = len(lines)
    while end > 0 and lines[end - 1].strip() == "":
        end -= 1
    if end == 0:
        return None
    start = end
    while start > 0 and lines[start - 1].strip() != "":
        start -= 1
    return start, end


def parse_expect(text: str) -> ExpectBlock | None:
    lines = text.splitlines()

    block_open_lines = [i for i, l in enumerate(lines) if l == BLOCK_OPEN]
    line_form_lines = [i for i, l in enumerate(lines) if l.startswith(LINE_PREFIX)]

    trailing = _trailing_nonblank_range(lines)

    if len(block_open_lines) > 1:
        raise DirectiveError(
            f"duplicate EXPECT block: found {len(block_open_lines)} '/* EXPECT' openings"
        )

    if block_open_lines:
        open_idx = block_open_lines[0]
        # Find the closing "*/" line after it.
        close_idx = None
        for i in range(open_idx + 1, len(lines)):
            if lines[i] == BLOCK_CLOSE:
                close_idx = i
                break
        if close_idx is None:
            raise DirectiveError("'/* EXPECT' block missing closing '*/'")
        # Everything after the closing "*/" must be blank (the block's own
        # content may legitimately contain blank lines, e.g. an empty
        # println() line, so we only check what follows the block).
        if any(l.strip() != "" for l in lines[close_idx + 1:]):
            raise DirectiveError("EXPECT block must be the last non-blank content of the file")
        if line_form_lines:
            raise DirectiveError("file mixes '/* EXPECT' block form and '// EXPECT:' line form")
        content = "\n".join(lines[open_idx + 1:close_idx])
        if content:
            content += "\n"
        return ExpectBlock(
            content_norm=normalize_output(content),
            start_line=open_idx + 1,
            end_line=close_idx + 1,
            form="block",
        )

    if line_form_lines:
        if trailing is None:
            raise DirectiveError("'// EXPECT:' lines must be the last non-blank content of the file")
        expected_range = set(range(trailing[0], trailing[1]))
        if set(line_form_lines) != expected_range:
            raise DirectiveError("'// EXPECT:' lines must be the last non-blank content of the file")
        content_lines = [l[len(LINE_PREFIX):].lstrip(" ") for l in lines[trailing[0]:trailing[1]]]
        content = "\n".join(content_lines) + "\n"
        return ExpectBlock(
            content_norm=normalize_output(content),
            start_line=trailing[0] + 1,
            end_line=trailing[1],
            form="line",
        )

    return None


def update_expect(text: str, actual_norm: str) -> str:
    """Rewrite (or append) the EXPECT block in `text` to match actual_norm.
    Touches nothing else in the file."""
    lines = text.splitlines()
    existing = None
    try:
        existing = parse_expect(text)
    except DirectiveError:
        existing = None

    desired_lines = actual_norm.splitlines()
    needs_escape = any(l == "*/" or l.startswith("*/") for l in desired_lines)

    if needs_escape:
        new_block = [f"{LINE_PREFIX}{(' ' + l) if l else ''}" for l in desired_lines]
    else:
        new_block = [BLOCK_OPEN] + desired_lines + [BLOCK_CLOSE]

    if existing is not None:
        before = lines[: existing.start_line - 1]
        after = lines[existing.end_line:]
        # Trim a single blank separator line already present before the block.
        new_lines = before + new_block + after
    else:
        before = lines
        while before and before[-1].strip() == "":
            before.pop()
        new_lines = before + [""] + new_block

    return "\n".join(new_lines) + "\n"


# ---------------------------------------------------------------------------
# //~ diagnostic annotations
# ---------------------------------------------------------------------------

_DIAG_RE = re.compile(
    r'^(?P<carets>\^*)\s*(?P<severity>ERROR|WARNING)\s+(?P<code>FS-[A-Z0-9]+-\d+)'
    r'(?:\s*@(?P<column>\d+))?'
    r'(?:\s*"(?P<message>[^"]*)")?\s*$'
)


@dataclass(frozen=True)
class DiagAnnotation:
    severity: str
    code: str
    target_line: int
    column: int | None
    message_substr: str | None
    anno_line: int  # physical line the //~ text sits on


@dataclass(frozen=True)
class ActualDiagnostic:
    severity: str
    code: str
    line: int
    column: int
    message: str = ""


def parse_diagnostic_annotations(text: str) -> list[DiagAnnotation]:
    lines = text.splitlines()
    annotations: list[DiagAnnotation] = []
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        pos = raw.find("//~")
        if pos == -1:
            continue
        payload = raw[pos + 3:]
        m = _DIAG_RE.match(payload.strip())
        if not m:
            raise DirectiveError(f"malformed //~ annotation: {raw!r}", line_no)
        carets = m.group("carets")
        target_line = line_no - len(carets)
        column = int(m.group("column")) if m.group("column") else None
        annotations.append(
            DiagAnnotation(
                severity=m.group("severity"),
                code=m.group("code"),
                target_line=target_line,
                column=column,
                message_substr=m.group("message"),
                anno_line=line_no,
            )
        )
    return annotations


def match_diagnostics(
    annotations: list[DiagAnnotation], actuals: list[ActualDiagnostic]
) -> tuple[list[DiagAnnotation], list[ActualDiagnostic]]:
    """Returns (missing_annotations, extra_actuals). Empty/empty = match."""
    remaining = list(actuals)
    missing: list[DiagAnnotation] = []

    with_col = [a for a in annotations if a.column is not None]
    without_col = [a for a in annotations if a.column is None]

    for anno in with_col:
        found = None
        for actual in remaining:
            if actual.code == anno.code and actual.line == anno.target_line and actual.column == anno.column:
                found = actual
                break
        if found is None:
            missing.append(anno)
        else:
            remaining.remove(found)

    for anno in without_col:
        found = None
        for actual in remaining:
            if actual.code == anno.code and actual.line == anno.target_line:
                found = actual
                break
        if found is None:
            missing.append(anno)
        else:
            remaining.remove(found)

    return missing, remaining


def update_diagnostic_annotations(text: str, actuals: list[ActualDiagnostic]) -> str:
    """Rewrite //~ annotations to match actuals.

    Always fully regenerates the annotation set from `actuals` rather than
    doing a minimal incremental diff against what's already on disk. An
    earlier incremental version kept individually-matched annotations
    untouched and only patched in the mismatched ones, recomputing caret
    counts (//~^, //~^^, ...) purely from the newly-inserted subset. When a
    stacked group had one diagnostic that stayed matched across a run and a
    sibling that didn't, that produced an inconsistent caret count for the
    group (e.g. two siblings both written with a single //~^, only one of
    which is actually correct) -- which itself changed what the *next*
    --update pass considered stale, so two same-code diagnostics at
    different columns on one line could swap which one got which caret
    count forever, never reaching a fixed point. Regenerating the whole
    line's group together, every time, is simpler and provably idempotent:
    for a fixed `actuals` list the output text is always identical.
    """
    lines = text.splitlines()

    # Strip every existing annotation line/segment, tracking where each
    # surviving code line lands in the stripped list (a line that was
    # nothing but an annotation disappears entirely, shifting everything
    # below it).
    orig_to_kept: dict[int, int] = {}
    kept_lines: list[str] = []
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        pos = raw.find("//~")
        if pos == -1:
            kept_lines.append(raw)
            orig_to_kept[line_no] = len(kept_lines) - 1
            continue
        code_part = raw[:pos].rstrip()
        if code_part == "":
            continue  # whole line was just the annotation; drop it
        kept_lines.append(code_part)
        orig_to_kept[line_no] = len(kept_lines) - 1

    by_line: dict[int, list[ActualDiagnostic]] = {}
    for a in actuals:
        by_line.setdefault(a.line, []).append(a)

    inserts: dict[int, list[ActualDiagnostic]] = {}
    for line_no, diags in by_line.items():
        kept_idx = orig_to_kept.get(line_no, len(kept_lines) - 1)
        inserts[kept_idx] = diags

    output: list[str] = []
    for idx, raw in enumerate(kept_lines):
        diags = inserts.get(idx)
        if not diags:
            output.append(raw)
            continue
        first, remaining = diags[0], diags[1:]
        col_part = f" @{first.column}" if first.column is not None else ""
        output.append(f"{raw}  //~ {first.severity} {first.code}{col_part}")
        for stack_offset, diag in enumerate(remaining, start=1):
            col_part = f" @{diag.column}" if diag.column is not None else ""
            output.append(f"//~{'^' * stack_offset} {diag.severity} {diag.code}{col_part}")

    return "\n".join(output) + "\n"
