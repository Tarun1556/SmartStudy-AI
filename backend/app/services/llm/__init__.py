from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import re
import random
import logging

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("studyapp.llm")


def safe_parse_json(raw: str, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not raw or not isinstance(raw, str):
        return default
    try:
        return json.loads(raw)
    except Exception:
        pass
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
    except Exception:
        pass
    try:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
    except Exception:
        pass
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = cleaned.strip().strip("`").strip()
        return json.loads(cleaned)
    except Exception:
        return default


def validate_or_repair_json(
    raw_response: str,
    is_array: bool,
    llm_provider,
    system_hint: str,
    user_hint: str,
    max_repair_attempts: int = 1,
) -> Any:
    default = [] if is_array else {}
    parsed = safe_parse_json(raw_response, None)
    if parsed is not None:
        if (is_array and isinstance(parsed, list)) or (not is_array and isinstance(parsed, dict)):
            return parsed
    attempt = 0
    repaired = raw_response
    while attempt < max_repair_attempts and hasattr(llm_provider, "_raw_chat"):
        attempt += 1
        try:
            sys_msg = (
                "You are a JSON repair assistant. The previous LLM response was not valid JSON. "
                "Return ONLY valid JSON with no extra text. Do not add commentary. "
                f"Expected JSON type: {'array' if is_array else 'object'}. "
                f"Hint about expected schema: {system_hint}"
            )
            usr_msg = (
                f"Original broken output:\n{repaired}\n\n"
                f"Context about what was requested:\n{user_hint}\n\n"
                "Return the repaired valid JSON ONLY."
            )
            repaired = llm_provider._raw_chat(sys_msg, usr_msg, json_mode=False)
            parsed = safe_parse_json(repaired, None)
            if parsed is not None:
                if (is_array and isinstance(parsed, list)) or (not is_array and isinstance(parsed, dict)):
                    return parsed
        except Exception as e:
            logger.warning(f"JSON repair attempt {attempt} failed: {e}")
            break
    return None


class LLMProvider(ABC):
    @abstractmethod
    def generate_structured_notes(self, chunks: List[str], title: str = "") -> Dict[str, Any]:
        ...

    @abstractmethod
    def extract_topics(self, text: str, notes: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def merge_topic_labels(self, candidate: str, existing: List[Dict[str, Any]]) -> Optional[str]:
        ...

    @abstractmethod
    def explain_topic(self, topic_name: str, evidence: List[str]) -> str:
        ...

    @abstractmethod
    def answer_question(self, question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def generate_quiz_questions(self, content: List[Dict[str, Any]], num_questions: int, quiz_type: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def generate_study_guide(self, topics: List[Dict[str, Any]], lectures: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...


class MockProvider(LLMProvider):
    def _parse_safe_json(self, data: Any, default: Any) -> Any:
        if isinstance(data, (dict, list)):
            return data
        return default

    def generate_structured_notes(self, chunks: List[str], title: str = "") -> Dict[str, Any]:
        combined = " ".join(chunks)[:5000] if chunks else ""
        sentences = [s.strip() for s in re.split(r'[.!?]+', combined) if s.strip() and len(s.strip()) > 20]
        sentences = sentences[:30]

        headings = []
        key_ideas = []
        definitions = []
        examples = []
        relationships = []
        refs = []

        keywords = self._extract_keywords(combined)

        for i, s in enumerate(sentences[:5]):
            headings.append({
                "id": f"h{i+1}",
                "text": f"Section {i+1}: {s[:80].rstrip()}...",
                "children": [],
            })

        for i, s in enumerate(sentences[:10]):
            key_ideas.append({
                "id": f"k{i+1}",
                "idea": s[:200].rstrip(),
                "source_ref": f"segment_{i % len(chunks) if chunks else 0}",
            })

        for i, kw in enumerate(keywords[:8]):
            if i < len(sentences):
                definitions.append({
                    "term": kw,
                    "definition": sentences[i][:150].rstrip(),
                    "source_ref": f"segment_{i}",
                })

        for i, s in enumerate(sentences[5:10]):
            examples.append({
                "description": f"Example {i+1} illustrating application",
                "text": s[:200].rstrip(),
                "source_ref": f"segment_{i+5}",
            })

        for i in range(min(3, len(keywords) - 1)):
            relationships.append({
                "from": keywords[i],
                "to": keywords[i+1],
                "relation": "related to",
            })

        for i in range(min(5, len(chunks))):
            refs.append({
                "segment_index": i,
                "source_type": "text",
                "snippet": chunks[i][:150] if chunks and i < len(chunks) else "",
            })

        return {
            "title": title or (f"Lecture Notes on {keywords[0]}" if keywords else "Lecture Notes"),
            "overview": (sentences[0] if sentences else "Overview of the lecture content")[:500],
            "headings": headings,
            "key_ideas": key_ideas,
            "definitions": definitions,
            "examples": examples,
            "relationships": relationships,
            "source_references": refs,
        }

    def extract_topics(self, text: str, notes: Dict[str, Any]) -> List[Dict[str, Any]]:
        keywords = self._extract_keywords(text)
        definitions = notes.get("definitions", []) if isinstance(notes, dict) else []

        topics = []
        seen = set()
        for d in definitions:
            if isinstance(d, dict) and d.get("term"):
                term = d["term"].strip().lower()
                if term not in seen and len(term) > 2:
                    seen.add(term)
                    topics.append({
                        "name": d["term"],
                        "description": d.get("definition", "")[:300],
                        "aliases": [d["term"]],
                        "confidence": 0.9,
                    })

        for kw in keywords:
            lower = kw.lower()
            if lower not in seen and len(kw) > 3:
                seen.add(lower)
                topics.append({
                    "name": kw,
                    "description": f"A key concept: {kw}",
                    "aliases": [kw],
                    "confidence": 0.7,
                })

        return topics[:25]

    def merge_topic_labels(self, candidate: str, existing: List[Dict[str, Any]]) -> Optional[str]:
        can_lower = candidate.strip().lower().rstrip("s")
        for ex in existing:
            ex_name = ex.get("name", "") if isinstance(ex, dict) else str(ex)
            aliases = ex.get("aliases", []) if isinstance(ex, dict) else []
            all_names = [ex_name] + list(aliases)
            for n in all_names:
                if n.strip().lower().rstrip("s") == can_lower:
                    return ex.get("canonical_name", ex_name) if isinstance(ex, dict) else n
        return None

    def explain_topic(self, topic_name: str, evidence: List[str]) -> str:
        ev_text = evidence[0] if evidence else ""
        return (
            f"{topic_name} is an important concept covered across the course. "
            f"It appears in multiple lectures with related supporting material. "
            f"Based on course content: {ev_text[:300]}"
        )

    def answer_question(self, question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not context_chunks:
            return {
                "answer": "I could not find relevant information about this in your uploaded lecture material. Please check if the topic is covered in your courses or try a different question.",
                "citations": [],
                "found_in_material": False,
            }

        chunks_text = [c.get("content", c.get("snippet", "")) for c in context_chunks[:5]]
        combined = " ".join(chunks_text)[:1200]
        citations = []
        for c in context_chunks[:5]:
            lecture_title = c.get("lecture_title", "Unknown Lecture")
            citations.append({
                "lecture_id": c.get("lecture_id"),
                "lecture_title": lecture_title,
                "lecture_number": c.get("lecture_number"),
                "snippet": c.get("snippet", c.get("content", ""))[:200],
                "start_time": c.get("start_time"),
            })

        q_lower = question.lower()
        answer_sentences = [s.strip() for s in re.split(r'[.!?]+', combined) if s.strip()]
        if len(answer_sentences) == 0:
            answer_sentences = [combined[:500]]

        answer = " ".join(answer_sentences[:5])
        if len(answer) < 50:
            answer = combined[:500]

        return {
            "answer": f"Based on your lecture material: {answer}\n\n(Sourced from {len(citations)} lecture reference(s))",
            "citations": citations,
            "found_in_material": True,
        }

    def generate_quiz_questions(self, content: List[Dict[str, Any]], num_questions: int, quiz_type: str) -> List[Dict[str, Any]]:
        questions = []
        sentences = []
        for c in content:
            txt = c.get("content", c.get("definition", ""))
            sentences.extend([s.strip() for s in re.split(r'[.!?]+', txt) if s.strip() and len(s) > 25])

        for i in range(min(num_questions, max(1, len(sentences) // 2))):
            src = content[i % len(content)] if content else {}
            correct = sentences[i * 2] if i * 2 < len(sentences) else sentences[-1]
            distractors = []
            for j in range(1, len(sentences)):
                idx = (i * 2 + j) % len(sentences)
                if len(distractors) >= 3:
                    break
                if sentences[idx] != correct:
                    distractors.append(sentences[idx][:120])

            while len(distractors) < 3:
                distractors.append(f"Option {len(distractors)+1}")

            term = src.get("term") or src.get("topic_name") or f"Concept {i+1}"

            questions.append({
                "question_type": "mcq",
                "question_text": f"Which of the following best describes {term}?",
                "options": [
                    correct[:120],
                    *distractors[:3],
                ],
                "correct_answer": correct[:120],
                "explanation": correct[:300],
                "source_lecture_id": src.get("lecture_id"),
                "source_topic_id": src.get("topic_id"),
                "source_context": correct[:200],
            })

        return questions

    def generate_study_guide(self, topics: List[Dict[str, Any]], lectures: List[Dict[str, Any]]) -> Dict[str, Any]:
        sorted_topics = sorted(topics, key=lambda t: t.get("coverage_score", 0), reverse=True)
        top_topics = []
        for t in sorted_topics[:15]:
            lecture_ids = t.get("lecture_ids", [])
            lecture_titles = [l.get("title", f"L{l.get('lecture_number','?')}") for l in lectures if l.get("id") in lecture_ids]
            top_topics.append({
                "topic_id": t.get("id"),
                "name": t.get("canonical_name", t.get("name")),
                "coverage_score": t.get("coverage_score", 0),
                "lecture_count": t.get("lecture_count", len(lecture_ids)),
                "evidence_count": t.get("evidence_count", 0),
                "summary": t.get("description", f"Recurring topic across {len(lecture_ids)} lectures."),
                "lectures": [
                    {"id": lid, "title": ttl}
                    for lid, ttl in zip(lecture_ids[:5], lecture_titles[:5])
                ],
            })

        return {
            "top_topics": top_topics,
            "lecture_summaries": [
                {"id": l.get("id"), "title": l.get("title"), "overview": l.get("overview", "")[:200]}
                for l in lectures[:10]
            ],
            "coverage_summary": {
                "total_topics": len(topics),
                "total_lectures": len(lectures),
                "high_coverage_topics": sum(1 for t in topics if t.get("coverage_score", 0) >= 0.5),
            },
        }

    def _extract_keywords(self, text: str) -> List[str]:
        # Full multi-word capitalized phrases first (e.g. "Binary Search Trees"),
        # so a 3+ word term isn't truncated into fragments like "binary search" / "trees".
        phrases = re.findall(r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)+\b', text)
        # Short ALL-CAPS acronyms (e.g. BST, FIFO, DFS).
        acronyms = re.findall(r'\b[A-Z]{2,6}\b', text)
        # Single capitalized words as a lower-priority fallback.
        single_caps = re.findall(r'\b[A-Z][a-z]{2,}\b', text)

        result: List[str] = []
        seen = set()

        def add(term: str) -> None:
            term = term.strip()
            key = term.lower()
            if key and key not in seen and 2 < len(term) < 60:
                seen.add(key)
                result.append(term)

        for group in (phrases, acronyms, single_caps):
            for term in group:
                add(term)

        return result[:30]


class _BaseHTTPProvider(LLMProvider):
    def __init__(self):
        try:
            import httpx
            self.client = httpx.Client(timeout=120.0, follow_redirects=True)
        except Exception:
            self.client = None

    def _raw_chat(self, system: str, user: str, json_mode: bool = True) -> str:
        raise NotImplementedError

    _TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def _raw_chat_retrying(self, system: str, user: str, json_mode: bool = True, retries: int = 1) -> str:
        import httpx
        import time as _time
        attempt = 0
        while True:
            try:
                return self._raw_chat(system, user, json_mode=json_mode)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else None
                if attempt < retries and status in self._TRANSIENT_STATUS_CODES:
                    attempt += 1
                    logger.warning(f"{type(self).__name__} transient HTTP {status}, retrying ({attempt}/{retries})...")
                    _time.sleep(1.5 * attempt)
                    continue
                raise
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt < retries:
                    attempt += 1
                    logger.warning(f"{type(self).__name__} network error ({e}), retrying ({attempt}/{retries})...")
                    _time.sleep(1.5 * attempt)
                    continue
                raise

    def _chat_json_object(self, system: str, user: str, schema_hint: str, fallback_result: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client:
            return fallback_result
        try:
            raw = self._raw_chat_retrying(system, user, json_mode=True)
            parsed = validate_or_repair_json(
                raw_response=raw,
                is_array=False,
                llm_provider=self,
                system_hint=schema_hint,
                user_hint=user[:800],
            )
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            logger.warning(f"{type(self).__name__} JSON object call failed: {e}")
        return fallback_result

    def _chat_json_array(self, system: str, user: str, schema_hint: str, fallback_result: List[Any]) -> List[Any]:
        if not self.client:
            return fallback_result
        try:
            raw = self._raw_chat_retrying(system, user, json_mode=True)
            parsed = validate_or_repair_json(
                raw_response=raw,
                is_array=True,
                llm_provider=self,
                system_hint=schema_hint,
                user_hint=user[:800],
            )
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.warning(f"{type(self).__name__} JSON array call failed: {e}")
        return fallback_result

    def _chat_text(self, system: str, user: str, fallback: str) -> str:
        if not self.client:
            return fallback
        try:
            return self._raw_chat_retrying(system, user, json_mode=False).strip()
        except Exception as e:
            logger.warning(f"{type(self).__name__} text call failed: {e}")
        return fallback


class OpenAIProvider(_BaseHTTPProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self._fallback = MockProvider()

    def _raw_chat(self, system: str, user: str, json_mode: bool = True) -> str:
        if not self.client or not self.api_key:
            raise RuntimeError("OpenAI provider not properly configured")
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self.client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def generate_structured_notes(self, chunks: List[str], title: str = "") -> Dict[str, Any]:
        fallback = self._fallback.generate_structured_notes(chunks, title)
        if not self.client or not self.api_key:
            return fallback
        schema = (
            "Object keys: title (string), overview (string), headings (array of {id,text,children[]}), "
            "key_ideas (array of {id,idea,source_ref}), definitions (array of {term,definition,source_ref}), "
            "examples (array of {description,text,source_ref}), relationships (array of {from,to,relation}), "
            "source_references (array of {segment_index,source_type,snippet})"
        )
        sys = (
            "You are an expert learning assistant that converts lecture content into structured study notes. "
            "Return ONLY a valid JSON object. "
            f"Expected schema: {schema}. "
            "Each definition and key idea must include a source_ref pointing to the chunk it came from. "
            "Be concise, thorough, and accurate. Do not invent content."
        )
        user_payload = {
            "title_hint": title,
            "chunks": chunks[:25],
            "total_chunks": len(chunks),
        }
        result = self._chat_json_object(sys, json.dumps(user_payload), schema, fallback)
        for required_key in ("title", "overview", "headings", "key_ideas", "definitions", "examples", "relationships", "source_references"):
            if required_key not in result:
                result[required_key] = fallback.get(required_key, [])
        return result

    def extract_topics(self, text: str, notes: Dict[str, Any]) -> List[Dict[str, Any]]:
        fallback = self._fallback.extract_topics(text, notes)
        if not self.client or not self.api_key:
            return fallback
        schema = (
            "Array of objects with: name (string), description (string), aliases (array of strings), confidence (0..1 number). "
            "Return 8-25 of the most important concepts."
        )
        sys = (
            "You are an expert at extracting key concepts, topics, and terminology from lecture notes. "
            "Return ONLY a valid JSON array. "
            f"Expected schema: {schema}. "
            "Focus on concepts a student would need to know for an exam. "
            "Provide reasonable aliases for each topic (e.g. BST -> Binary Search Tree). "
            "confidence should reflect how central the topic is to the material."
        )
        notes_snippet = json.dumps({
            "overview": notes.get("overview", "") if isinstance(notes, dict) else "",
            "definitions": notes.get("definitions", []) if isinstance(notes, dict) else [],
            "key_ideas": notes.get("key_ideas", []) if isinstance(notes, dict) else [],
        })[:3000]
        user_payload = f"Lecture transcript excerpt:\n{text[:5000]}\n\nStructured notes excerpt:\n{notes_snippet}\n\nExtract the most important topics."
        result = self._chat_json_array(sys, user_payload, schema, fallback)
        if not result:
            return fallback
        cleaned = []
        for t in result:
            if not isinstance(t, dict) or not t.get("name"):
                continue
            cleaned.append({
                "name": str(t["name"]).strip()[:200],
                "description": str(t.get("description", ""))[:500],
                "aliases": [a for a in (t.get("aliases") or []) if isinstance(a, str)][:10],
                "confidence": float(t.get("confidence", 0.7)),
            })
        return cleaned[:30] or fallback

    def merge_topic_labels(self, candidate: str, existing: List[Dict[str, Any]]) -> Optional[str]:
        return self._fallback.merge_topic_labels(candidate, existing)

    def explain_topic(self, topic_name: str, evidence: List[str]) -> str:
        fallback = self._fallback.explain_topic(topic_name, evidence)
        if not self.client or not self.api_key:
            return fallback
        sys = (
            "You are an expert study guide author. Given a topic name and 2-4 evidence snippets from a student's lecture notes, "
            "produce a 2-4 sentence explanation that synthesizes what the student's own notes say about the topic. "
            "Do NOT bring in outside knowledge not present in the evidence. "
            "Be concise, clear, and pedagogical."
        )
        user_payload = f"Topic: {topic_name}\n\nEvidence snippets from student notes:\n"
        for i, ev in enumerate(evidence[:4]):
            user_payload += f"[{i+1}] {ev[:400]}\n\n"
        return self._chat_text(sys, user_payload, fallback)

    def answer_question(self, question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.answer_question(question, context_chunks)
        if not self.client or not self.api_key:
            return fallback
        if not context_chunks:
            return fallback
        schema = (
            "Object with: answer (string), found_in_material (boolean), "
            "citations (array of {lecture_id:number|null, lecture_title:string, lecture_number:number|null, snippet:string, start_time:number|null})"
        )
        sys = (
            "You are a grounded Q&A assistant that only answers using the student's provided lecture material. "
            "You must NEVER invent facts or draw on outside knowledge. "
            "Return ONLY a valid JSON object. "
            f"Expected schema: {schema}. "
            "Instructions:\n"
            "1. Read the user's question carefully.\n"
            "2. Find relevant sentences only in the provided context chunks.\n"
            "3. If no chunk addresses the question meaningfully: set found_in_material=false, answer='I could not find relevant information about this in your uploaded lecture material.', citations=[]\n"
            "4. Otherwise: synthesize a concise answer strictly from chunks, set found_in_material=true, and include 1-5 citations of the source chunks used.\n"
            "5. Each citation MUST include the lecture_title and snippet from the chunk. Keep snippet under 250 chars."
        )
        ctx = []
        for i, c in enumerate(context_chunks[:8]):
            ctx.append({
                "idx": i + 1,
                "lecture_id": c.get("lecture_id"),
                "lecture_title": c.get("lecture_title", "Unknown Lecture"),
                "lecture_number": c.get("lecture_number"),
                "content": c.get("content", c.get("snippet", ""))[:800],
                "start_time": c.get("start_time"),
            })
        user_payload = f"QUESTION: {question}\n\nPROVIDED CONTEXT CHUNKS (student's own material only):\n{json.dumps(ctx, default=str)}\n\nAnswer the question using ONLY the provided context."
        result = self._chat_json_object(sys, user_payload, schema, None)
        if not isinstance(result, dict) or "answer" not in result:
            return fallback
        citations_raw = result.get("citations") or []
        citations = []
        for c in citations_raw:
            if not isinstance(c, dict):
                continue
            lid = c.get("lecture_id")
            try:
                if lid is not None:
                    lid = int(lid)
            except (ValueError, TypeError):
                lid = None
            citations.append({
                "lecture_id": lid,
                "lecture_title": str(c.get("lecture_title", "Unknown Lecture")),
                "lecture_number": c.get("lecture_number"),
                "snippet": str(c.get("snippet", ""))[:300],
                "start_time": c.get("start_time"),
            })
        found = bool(result.get("found_in_material", False)) and len(citations) > 0
        answer = str(result.get("answer", ""))
        if not answer:
            return fallback
        return {
            "answer": answer,
            "citations": citations,
            "found_in_material": found,
        }

    def generate_quiz_questions(self, content: List[Dict[str, Any]], num_questions: int, quiz_type: str) -> List[Dict[str, Any]]:
        fallback = self._fallback.generate_quiz_questions(content, num_questions, quiz_type)
        if not self.client or not self.api_key:
            return fallback
        schema = (
            "Array of objects with: question_type ('mcq'), question_text (string), options (array of 4 strings), "
            "correct_answer (string, must match one option exactly), explanation (string), "
            "source_lecture_id (number|null), source_topic_id (number|null), source_context (string)."
        )
        sys = (
            "You are an expert pedagogical quiz creator. Using ONLY the student's provided lecture material, generate MCQ practice questions. "
            "Return ONLY a valid JSON array. "
            f"Expected schema: {schema}. "
            f"Generate exactly {num_questions} questions. The correct_answer MUST appear in the options array. "
            "Each question should test understanding, not rote memorization. "
            "Always include source_context (2-3 sentences from the material) and source_lecture_id when known."
        )
        trimmed = []
        for c in content[:40]:
            trimmed.append({
                "topic_name": c.get("topic_name") or c.get("canonical_name") or c.get("name"),
                "term": c.get("term"),
                "definition": c.get("definition", "")[:400],
                "content": c.get("content", c.get("summary", ""))[:600],
                "lecture_id": c.get("lecture_id"),
                "topic_id": c.get("topic_id"),
            })
        user_payload = f"Source material (student's own notes only):\n{json.dumps(trimmed, default=str)}\n\nQuiz type: {quiz_type}\nNumber of questions: {num_questions}"
        result = self._chat_json_array(sys, user_payload, schema, fallback)
        if not isinstance(result, list) or not result:
            return fallback
        cleaned = []
        for q in result:
            if not isinstance(q, dict):
                continue
            opts = q.get("options") or []
            correct = q.get("correct_answer") or ""
            if len(opts) < 2 or correct not in opts:
                continue
            cleaned.append({
                "question_type": str(q.get("question_type", "mcq")),
                "question_text": str(q.get("question_text", "")),
                "options": [str(o)[:300] for o in opts][:6],
                "correct_answer": str(correct)[:300],
                "explanation": str(q.get("explanation", "")),
                "source_lecture_id": q.get("source_lecture_id"),
                "source_topic_id": q.get("source_topic_id"),
                "source_context": str(q.get("source_context", ""))[:400],
            })
        return cleaned[:num_questions] or fallback

    def generate_study_guide(self, topics: List[Dict[str, Any]], lectures: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.generate_study_guide(topics, lectures)
        if not self.client or not self.api_key:
            return fallback
        schema = (
            "Object with: top_topics (array of {topic_id:number, name:string, coverage_score:number, lecture_count:number, "
            "evidence_count:number, summary:string, lectures:[{id,title}]}), "
            "lecture_summaries (array of {id:number, title:string, overview:string}), "
            "coverage_summary ({total_topics:number, total_lectures:number, high_coverage_topics:number})"
        )
        sys = (
            "You are an expert study-guide compiler. Given a list of topics with coverage scores and a list of lectures, "
            "synthesize a comprehensive semester study guide. "
            "Return ONLY a valid JSON object. "
            f"Expected schema: {schema}. "
            "Sort top_topics by coverage_score descending. Limit to 15 top topics. "
            "Each topic summary should be 2-3 sentences explaining why the topic matters, using ONLY what is provided. "
            "Do NOT invent outside content."
        )
        t_trimmed = []
        for t in (sorted(topics, key=lambda x: x.get("coverage_score", 0), reverse=True))[:25]:
            t_trimmed.append({
                "id": t.get("id"),
                "name": t.get("name"),
                "canonical_name": t.get("canonical_name"),
                "description": t.get("description", "")[:400],
                "coverage_score": t.get("coverage_score", 0),
                "lecture_count": t.get("lecture_count", 0),
                "evidence_count": t.get("evidence_count", 0),
                "lecture_ids": t.get("lecture_ids", [])[:8],
            })
        l_trimmed = []
        for l in lectures[:20]:
            l_trimmed.append({
                "id": l.get("id"),
                "title": l.get("title"),
                "lecture_number": l.get("lecture_number"),
                "overview": str(l.get("overview", ""))[:500],
            })
        user_payload = f"Topics (sorted by coverage):\n{json.dumps(t_trimmed)}\n\nLectures:\n{json.dumps(l_trimmed)}"
        result = self._chat_json_object(sys, user_payload, schema, None)
        if not isinstance(result, dict) or "top_topics" not in result:
            return fallback
        for req in ("top_topics", "lecture_summaries", "coverage_summary"):
            if req not in result:
                result[req] = fallback.get(req, [] if req != "coverage_summary" else {})
        return result


class AnthropicProvider(_BaseHTTPProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self._fallback = MockProvider()

    def _raw_chat(self, system: str, user: str, json_mode: bool = True) -> str:
        if not self.client or not self.api_key:
            raise RuntimeError("Anthropic provider not properly configured")
        prefill = '{' if json_mode else ''
        messages = [{"role": "user", "content": user}]
        if prefill:
            messages.append({"role": "assistant", "content": prefill})
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": system,
            "messages": messages,
        }
        r = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        blocks = data.get("content", [])
        raw = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
        return prefill + raw

    def generate_structured_notes(self, chunks: List[str], title: str = "") -> Dict[str, Any]:
        fallback = self._fallback.generate_structured_notes(chunks, title)
        if not self.client or not self.api_key:
            return fallback
        sys = (
            "You are an expert learning assistant that converts lecture content into structured study notes. "
            "Return ONLY valid JSON. Do not include any explanatory prose before or after the JSON. "
            "Required keys: title, overview, headings[{id,text,children[]}], "
            "key_ideas[{id,idea,source_ref}], definitions[{term,definition,source_ref}], "
            "examples[{description,text,source_ref}], relationships[{from,to,relation}], "
            "source_references[{segment_index,source_type,snippet}]."
        )
        user_payload = json.dumps({
            "title_hint": title,
            "chunks": chunks[:25],
            "total_chunks": len(chunks),
        })
        return self._chat_json_object(sys, user_payload, "structured notes JSON", fallback) or fallback

    def extract_topics(self, text: str, notes: Dict[str, Any]) -> List[Dict[str, Any]]:
        fallback = self._fallback.extract_topics(text, notes)
        if not self.client or not self.api_key:
            return fallback
        sys = (
            "You extract core concepts, topics, and terminology from lecture material. "
            "Return ONLY a valid JSON array. Do not add prose. "
            "Each object must have: name, description, aliases[string[]], confidence(0..1). "
            "Return 8-25 of the most important exam-relevant topics."
        )
        notes_snippet = json.dumps({
            "overview": notes.get("overview", "") if isinstance(notes, dict) else "",
            "definitions": notes.get("definitions", []) if isinstance(notes, dict) else [],
        })[:3000]
        user_payload = f"Lecture transcript excerpt:\n{text[:5000]}\n\nStructured notes:\n{notes_snippet}\n\nExtract important topics as JSON array."
        result = self._chat_json_array(sys, user_payload, "topics JSON array", fallback) or fallback
        if not result:
            return fallback
        cleaned = []
        for t in result:
            if isinstance(t, dict) and t.get("name"):
                cleaned.append({
                    "name": str(t["name"]).strip()[:200],
                    "description": str(t.get("description", ""))[:500],
                    "aliases": [a for a in (t.get("aliases") or []) if isinstance(a, str)][:10],
                    "confidence": float(t.get("confidence", 0.7)),
                })
        return cleaned[:30] or fallback

    def merge_topic_labels(self, candidate: str, existing: List[Dict[str, Any]]) -> Optional[str]:
        return self._fallback.merge_topic_labels(candidate, existing)

    def explain_topic(self, topic_name: str, evidence: List[str]) -> str:
        fallback = self._fallback.explain_topic(topic_name, evidence)
        if not self.client or not self.api_key:
            return fallback
        sys = "Synthesize a 2-4 sentence explanation of the topic using ONLY the provided evidence snippets from the student's notes. No outside knowledge."
        ev = "\n".join(f"[{i+1}] {e[:400]}" for i, e in enumerate(evidence[:4]))
        return self._chat_text(sys, f"Topic: {topic_name}\nEvidence:\n{ev}", fallback)

    def answer_question(self, question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.answer_question(question, context_chunks)
        if not self.client or not self.api_key or not context_chunks:
            return fallback
        sys = (
            "You are a grounded Q&A assistant. Use ONLY the student's provided lecture chunks. "
            "Return ONLY valid JSON with keys: answer(string), found_in_material(boolean), "
            "citations[{lecture_id,lecture_title,lecture_number,snippet,start_time}]. "
            "If no answer exists: found_in_material=false, answer='I could not find relevant information about this in your uploaded lecture material.', citations=[]."
        )
        ctx = [
            {
                "lecture_id": c.get("lecture_id"),
                "lecture_title": c.get("lecture_title", "Unknown"),
                "lecture_number": c.get("lecture_number"),
                "content": c.get("content", c.get("snippet", ""))[:800],
                "start_time": c.get("start_time"),
            }
            for c in context_chunks[:8]
        ]
        user_payload = f"QUESTION: {question}\nCONTEXT:\n{json.dumps(ctx, default=str)}"
        result = self._chat_json_object(sys, user_payload, "answer JSON", None)
        if not isinstance(result, dict) or "answer" not in result:
            return fallback
        citations_raw = result.get("citations") or []
        citations = []
        for c in citations_raw:
            if not isinstance(c, dict):
                continue
            lid = c.get("lecture_id")
            try:
                lid = int(lid) if lid is not None else None
            except (ValueError, TypeError):
                lid = None
            citations.append({
                "lecture_id": lid,
                "lecture_title": str(c.get("lecture_title", "Unknown")),
                "lecture_number": c.get("lecture_number"),
                "snippet": str(c.get("snippet", ""))[:300],
                "start_time": c.get("start_time"),
            })
        return {
            "answer": str(result.get("answer", fallback["answer"])),
            "citations": citations,
            "found_in_material": bool(result.get("found_in_material")) and len(citations) > 0,
        }

    def generate_quiz_questions(self, content: List[Dict[str, Any]], num_questions: int, quiz_type: str) -> List[Dict[str, Any]]:
        fallback = self._fallback.generate_quiz_questions(content, num_questions, quiz_type)
        if not self.client or not self.api_key:
            return fallback
        sys = (
            "Generate MCQ quiz questions from student's own notes only. "
            "Return ONLY valid JSON array. Each object: question_type, question_text, options[4], correct_answer, explanation, source_lecture_id, source_topic_id, source_context. "
            "correct_answer must exactly match one option."
        )
        trimmed = [
            {
                "topic_name": c.get("topic_name") or c.get("canonical_name"),
                "term": c.get("term"),
                "definition": c.get("definition", "")[:400],
                "content": c.get("content", c.get("summary", ""))[:600],
                "lecture_id": c.get("lecture_id"),
            }
            for c in content[:40]
        ]
        user_payload = f"Material:\n{json.dumps(trimmed)}\nCount: {num_questions}. Type: {quiz_type}."
        result = self._chat_json_array(sys, user_payload, "quiz JSON array", fallback) or fallback
        if not isinstance(result, list):
            return fallback
        cleaned = []
        for q in result:
            if not isinstance(q, dict):
                continue
            opts = q.get("options") or []
            correct = q.get("correct_answer") or ""
            if len(opts) < 2 or correct not in opts:
                continue
            cleaned.append({
                "question_type": str(q.get("question_type", "mcq")),
                "question_text": str(q.get("question_text", "")),
                "options": [str(o)[:300] for o in opts][:6],
                "correct_answer": str(correct)[:300],
                "explanation": str(q.get("explanation", "")),
                "source_lecture_id": q.get("source_lecture_id"),
                "source_topic_id": q.get("source_topic_id"),
                "source_context": str(q.get("source_context", ""))[:400],
            })
        return cleaned[:num_questions] or fallback

    def generate_study_guide(self, topics: List[Dict[str, Any]], lectures: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.generate_study_guide(topics, lectures)
        if not self.client or not self.api_key:
            return fallback
        sys = (
            "Compile a semester study guide JSON. Keys: top_topics[15] ({topic_id,name,coverage_score,lecture_count,evidence_count,summary,lectures[{id,title}]}), "
            "lecture_summaries[{id,title,overview}], coverage_summary{total_topics,total_lectures,high_coverage_topics}. "
            "Order top_topics by coverage_score desc. No outside content."
        )
        t_trimmed = [
            {
                "id": t.get("id"), "canonical_name": t.get("canonical_name", t.get("name")),
                "description": t.get("description", "")[:400], "coverage_score": t.get("coverage_score", 0),
                "lecture_count": t.get("lecture_count"), "lecture_ids": t.get("lecture_ids", [])[:8],
            }
            for t in sorted(topics, key=lambda x: x.get("coverage_score", 0), reverse=True)[:25]
        ]
        l_trimmed = [
            {"id": l.get("id"), "title": l.get("title"), "lecture_number": l.get("lecture_number"),
             "overview": str(l.get("overview", ""))[:500]}
            for l in lectures[:20]
        ]
        user_payload = f"Topics:\n{json.dumps(t_trimmed)}\nLectures:\n{json.dumps(l_trimmed)}"
        result = self._chat_json_object(sys, user_payload, "study guide JSON", fallback) or fallback
        return result if isinstance(result, dict) else fallback


class GeminiProvider(_BaseHTTPProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self._fallback = MockProvider()

    def _raw_chat(self, system: str, user: str, json_mode: bool = True) -> str:
        if not self.client or not self.api_key:
            raise RuntimeError("Gemini provider not properly configured")
        config: Dict[str, Any] = {"temperature": 0.2}
        if json_mode:
            config["response_mime_type"] = "application/json"
        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": f"System instructions:\n{system}\n\nUser request:\n{user}"},
                ],
            }
        ]
        body = {"contents": contents, "generationConfig": config}
        r = self.client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected Gemini response format: {data}")

    def generate_structured_notes(self, chunks: List[str], title: str = "") -> Dict[str, Any]:
        fallback = self._fallback.generate_structured_notes(chunks, title)
        if not self.client or not self.api_key:
            return fallback
        sys = "Return ONLY valid JSON object with keys: title, overview, headings[{id,text,children[]}], key_ideas[{id,idea,source_ref}], definitions[{term,definition,source_ref}], examples[{description,text,source_ref}], relationships[{from,to,relation}], source_references[{segment_index,source_type,snippet}]."
        user_payload = json.dumps({"title_hint": title, "chunks": chunks[:25]})
        return self._chat_json_object(sys, user_payload, "structured notes", fallback) or fallback

    def extract_topics(self, text: str, notes: Dict[str, Any]) -> List[Dict[str, Any]]:
        fallback = self._fallback.extract_topics(text, notes)
        if not self.client or not self.api_key:
            return fallback
        sys = "Return ONLY valid JSON array of {name, description, aliases[string[]], confidence 0..1}. 8-25 most important exam topics. No prose."
        notes_snippet = json.dumps({
            "overview": notes.get("overview", "") if isinstance(notes, dict) else "",
            "definitions": notes.get("definitions", []) if isinstance(notes, dict) else [],
        })[:3000]
        user_payload = f"Transcript:\n{text[:5000]}\n\nNotes:\n{notes_snippet}"
        result = self._chat_json_array(sys, user_payload, "topics array", fallback) or fallback
        if not result:
            return fallback
        cleaned = []
        for t in result:
            if isinstance(t, dict) and t.get("name"):
                cleaned.append({
                    "name": str(t["name"]).strip()[:200],
                    "description": str(t.get("description", ""))[:500],
                    "aliases": [a for a in (t.get("aliases") or []) if isinstance(a, str)][:10],
                    "confidence": float(t.get("confidence", 0.7)),
                })
        return cleaned[:30] or fallback

    def merge_topic_labels(self, candidate: str, existing: List[Dict[str, Any]]) -> Optional[str]:
        return self._fallback.merge_topic_labels(candidate, existing)

    def explain_topic(self, topic_name: str, evidence: List[str]) -> str:
        fallback = self._fallback.explain_topic(topic_name, evidence)
        if not self.client or not self.api_key:
            return fallback
        sys = "Write a 2-4 sentence explanation of the topic using ONLY the evidence snippets from the student's notes. No outside knowledge."
        ev = "\n".join(f"[{i+1}] {e[:400]}" for i, e in enumerate(evidence[:4]))
        return self._chat_text(sys, f"Topic: {topic_name}\nEvidence:\n{ev}", fallback)

    def answer_question(self, question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.answer_question(question, context_chunks)
        if not self.client or not self.api_key or not context_chunks:
            return fallback
        sys = "Return ONLY valid JSON. Keys: answer(string), found_in_material(boolean), citations[{lecture_id,lecture_title,lecture_number,snippet,start_time}]. If no info in context: found_in_material=false + standard not-found answer + citations=[]."
        ctx = [
            {
                "lecture_id": c.get("lecture_id"), "lecture_title": c.get("lecture_title", "Unknown"),
                "lecture_number": c.get("lecture_number"), "content": c.get("content", c.get("snippet", ""))[:800],
                "start_time": c.get("start_time"),
            }
            for c in context_chunks[:8]
        ]
        user_payload = f"QUESTION: {question}\nCONTEXT:\n{json.dumps(ctx, default=str)}"
        result = self._chat_json_object(sys, user_payload, "answer JSON", None)
        if not isinstance(result, dict) or "answer" not in result:
            return fallback
        citations_raw = result.get("citations") or []
        citations = []
        for c in citations_raw:
            if not isinstance(c, dict):
                continue
            lid = c.get("lecture_id")
            try:
                lid = int(lid) if lid is not None else None
            except (ValueError, TypeError):
                lid = None
            citations.append({
                "lecture_id": lid, "lecture_title": str(c.get("lecture_title", "Unknown")),
                "lecture_number": c.get("lecture_number"), "snippet": str(c.get("snippet", ""))[:300],
                "start_time": c.get("start_time"),
            })
        return {
            "answer": str(result.get("answer", fallback["answer"])),
            "citations": citations,
            "found_in_material": bool(result.get("found_in_material")) and len(citations) > 0,
        }

    def generate_quiz_questions(self, content: List[Dict[str, Any]], num_questions: int, quiz_type: str) -> List[Dict[str, Any]]:
        fallback = self._fallback.generate_quiz_questions(content, num_questions, quiz_type)
        if not self.client or not self.api_key:
            return fallback
        sys = "Return ONLY valid JSON array of MCQ objects: question_type,question_text,options[4],correct_answer,explanation,source_lecture_id,source_topic_id,source_context. correct_answer must be in options. Use ONLY provided material."
        trimmed = [
            {
                "topic_name": c.get("topic_name") or c.get("canonical_name"),
                "term": c.get("term"), "definition": c.get("definition", "")[:400],
                "content": c.get("content", c.get("summary", ""))[:600], "lecture_id": c.get("lecture_id"),
            }
            for c in content[:40]
        ]
        user_payload = f"Material:\n{json.dumps(trimmed)}\nCount: {num_questions}. Type: {quiz_type}."
        result = self._chat_json_array(sys, user_payload, "quiz array", fallback) or fallback
        if not isinstance(result, list):
            return fallback
        cleaned = []
        for q in result:
            if not isinstance(q, dict):
                continue
            opts = q.get("options") or []
            correct = q.get("correct_answer") or ""
            if len(opts) < 2 or correct not in opts:
                continue
            cleaned.append({
                "question_type": str(q.get("question_type", "mcq")),
                "question_text": str(q.get("question_text", "")),
                "options": [str(o)[:300] for o in opts][:6],
                "correct_answer": str(correct)[:300],
                "explanation": str(q.get("explanation", "")),
                "source_lecture_id": q.get("source_lecture_id"),
                "source_topic_id": q.get("source_topic_id"),
                "source_context": str(q.get("source_context", ""))[:400],
            })
        return cleaned[:num_questions] or fallback

    def generate_study_guide(self, topics: List[Dict[str, Any]], lectures: List[Dict[str, Any]]) -> Dict[str, Any]:
        fallback = self._fallback.generate_study_guide(topics, lectures)
        if not self.client or not self.api_key:
            return fallback
        sys = "Return ONLY valid JSON. Keys: top_topics[15]{topic_id,name,coverage_score,lecture_count,evidence_count,summary,lectures[{id,title}]}, lecture_summaries[{id,title,overview}], coverage_summary{total_topics,total_lectures,high_coverage_topics}. Sort top_topics by coverage_score desc. No outside content."
        t_trimmed = [
            {
                "id": t.get("id"), "canonical_name": t.get("canonical_name", t.get("name")),
                "description": t.get("description", "")[:400], "coverage_score": t.get("coverage_score", 0),
                "lecture_count": t.get("lecture_count"), "lecture_ids": t.get("lecture_ids", [])[:8],
            }
            for t in sorted(topics, key=lambda x: x.get("coverage_score", 0), reverse=True)[:25]
        ]
        l_trimmed = [
            {"id": l.get("id"), "title": l.get("title"), "lecture_number": l.get("lecture_number"),
             "overview": str(l.get("overview", ""))[:500]}
            for l in lectures[:20]
        ]
        user_payload = f"Topics:\n{json.dumps(t_trimmed)}\nLectures:\n{json.dumps(l_trimmed)}"
        result = self._chat_json_object(sys, user_payload, "study guide JSON", fallback) or fallback
        return result if isinstance(result, dict) else fallback


_provider_cache: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _provider_cache
    if _provider_cache is not None:
        return _provider_cache
    provider_name = settings.LLM_PROVIDER.lower().strip()
    provider: LLMProvider
    if provider_name == "openai" and settings.OPENAI_API_KEY:
        provider = OpenAIProvider(settings.OPENAI_API_KEY)
    elif provider_name == "anthropic" and settings.ANTHROPIC_API_KEY:
        provider = AnthropicProvider(settings.ANTHROPIC_API_KEY)
    elif provider_name in ("gemini", "google") and settings.GOOGLE_API_KEY:
        provider = GeminiProvider(settings.GOOGLE_API_KEY)
    else:
        if provider_name != "mock" and provider_name not in ("openai", "anthropic", "gemini", "google"):
            logger.warning(
                "Unknown LLM_PROVIDER=%r (expected one of: openai, anthropic, gemini/google, mock). "
                "Falling back to MockProvider.", settings.LLM_PROVIDER,
            )
        elif provider_name != "mock":
            logger.warning(
                "LLM_PROVIDER=%r is set but its API key is missing. Falling back to MockProvider.",
                settings.LLM_PROVIDER,
            )
        provider = MockProvider()
    _provider_cache = provider
    return provider
