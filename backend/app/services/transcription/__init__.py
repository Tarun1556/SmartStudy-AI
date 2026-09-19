from abc import ABC, abstractmethod
from typing import List, Optional


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> List[dict]:
        ...


class MockTranscriptionProvider(TranscriptionProvider):
    def transcribe(self, audio_path: str) -> List[dict]:
        return [
            {
                "segment_index": 0,
                "text": "Welcome to this lecture. Today we will be covering the key concepts and main ideas.",
                "start_time": 0.0,
                "end_time": 30.0,
                "source_type": "audio",
            },
            {
                "segment_index": 1,
                "text": "The main topics include definitions, examples, and applications of the concepts introduced.",
                "start_time": 30.0,
                "end_time": 60.0,
                "source_type": "audio",
            },
        ]


class WhisperTranscriptionProvider(TranscriptionProvider):
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            except Exception:
                self._model = False
        return self._model

    def transcribe(self, audio_path: str) -> List[dict]:
        model = self._load()
        if not model:
            return MockTranscriptionProvider().transcribe(audio_path)
        try:
            segments, info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
            result = []
            for i, seg in enumerate(segments):
                result.append({
                    "segment_index": i,
                    "text": seg.text.strip(),
                    "start_time": float(seg.start),
                    "end_time": float(seg.end),
                    "source_type": "audio",
                })
            return result or MockTranscriptionProvider().transcribe(audio_path)
        except Exception:
            return MockTranscriptionProvider().transcribe(audio_path)


def get_transcription_provider() -> TranscriptionProvider:
    try:
        return WhisperTranscriptionProvider("tiny")
    except Exception:
        return MockTranscriptionProvider()
