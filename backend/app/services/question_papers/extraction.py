"""Question-boundary-aware segmentation of extracted question-paper text.

Unlike app/services/extraction._text_to_segments (a generic sentence-boundary
chunker built for lecture transcripts), this splits on the structural markers
that actually appear in exam papers: section headers ("SECTION A", "Part B"),
question numbering ("1.", "Q3", "1(a)"), and marks annotations ("[10 marks]").

Formats vary a lot across institutions, so this is deliberately heuristic and
conservative: if no question-number pattern is found anywhere in the text,
the whole text becomes a single preserved block rather than being discarded
or mis-split. Every regex-identified block always keeps its original text
verbatim in `question_text` — only `question_number`/`section`/`marks` are
best-effort metadata layered on top.
"""
import re
from typing import List, Optional, TypedDict


class QuestionBlock(TypedDict):
    question_number: Optional[str]
    section: Optional[str]
    question_text: str
    marks: Optional[int]


_SECTION_RE = re.compile(
    r'^\s*(?:SECTION|Section|PART|Part)[\s\-:]*([A-Z0-9]+)\b.*$'
)

# Matches a new top-level question number at the start of a line, optionally
# followed by a sub-part letter: "1.", "1)", "Q1", "Q.1", "1(a)", "1 a)".
_QUESTION_NUM_RE = re.compile(
    r'^\s*(?:Q\.?\s*)?(\d{1,3})\s*(?:\(([a-hA-H])\)|([a-hA-H])[\.\)])?\s*[\.\):\-]?\s+'
)

# A sub-part continuing the current question number: "(a)", "a)", "(i)".
_SUBPART_RE = re.compile(r'^\s*\(?([a-hA-H]|[ivx]{1,4})\)\s+')

# "[10 marks]", "(10 Marks)", "10 marks", "[10M]", "(5M)" — requires an
# explicit marks/M keyword so a bare number (e.g. a year) never matches.
_MARKS_RE = re.compile(r'[\[\(]?\s*(\d{1,3})\s*(?:marks?|Marks?|M)\s*[\]\)]?')


def _extract_marks(text: str) -> Optional[int]:
    m = _MARKS_RE.search(text)
    if not m:
        return None
    try:
        val = int(m.group(1))
        return val if 0 < val <= 100 else None
    except ValueError:
        return None


def segment_question_paper(raw_text: str) -> List[QuestionBlock]:
    if not raw_text or not raw_text.strip():
        return []

    lines = raw_text.splitlines()
    blocks: List[QuestionBlock] = []
    current_section: Optional[str] = None
    current_number: Optional[str] = None
    buffer_lines: List[str] = []

    def flush() -> None:
        text = "\n".join(buffer_lines).strip()
        text = re.sub(r'[ \t]+', ' ', text)
        if text:
            blocks.append(QuestionBlock(
                question_number=current_number,
                section=current_section,
                question_text=text,
                marks=_extract_marks(text),
            ))
        buffer_lines.clear()

    any_question_number_found = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        sec_match = _SECTION_RE.match(stripped)
        if sec_match and len(stripped) < 80:
            flush()
            current_section = sec_match.group(1)
            current_number = None
            continue

        num_match = _QUESTION_NUM_RE.match(stripped)
        if num_match:
            any_question_number_found = True
            flush()
            main_num = num_match.group(1)
            sub = num_match.group(2) or num_match.group(3)
            current_number = f"{main_num}({sub})" if sub else main_num
            remainder = stripped[num_match.end():]
            if remainder:
                buffer_lines.append(remainder)
            continue

        sub_match = _SUBPART_RE.match(stripped)
        if sub_match and current_number and buffer_lines:
            # A lettered sub-part under the current question number starts a
            # new block (e.g. "1(a)"/"1(b)") rather than being appended to it.
            flush()
            base_num = re.sub(r'\(.*\)$', '', current_number)
            current_number = f"{base_num}({sub_match.group(1)})"
            remainder = stripped[sub_match.end():]
            if remainder:
                buffer_lines.append(remainder)
            continue

        buffer_lines.append(stripped)

    flush()

    if not any_question_number_found:
        # Unknown/unsupported format: preserve everything as one block instead
        # of guessing at structure that isn't there.
        text = re.sub(r'\s+', ' ', raw_text).strip()
        return [QuestionBlock(
            question_number=None,
            section=None,
            question_text=text,
            marks=_extract_marks(text),
        )] if text else []

    return [b for b in blocks if b["question_text"]]
