import os
import io
import time
import numpy as np
import soundfile as sf
from typing import Optional

try:
    from kokoro import KPipeline
    from langdetect import detect
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


class MultilingualTTSEngine:
    """
    Offline local TTS Engine based on Kokoro.
    Supported languages: English, Spanish, French, Italian, Portuguese.
    """
    LANG_CODES = {
        "en-us": "a", "en-gb": "b",
        "es": "e", "fr": "f", "it": "i", "pt-br": "p",
    }
    DEFAULT_VOICES = {
        "en-us": "af_heart", "en-gb": "bf_emma",
        "es": "ef_dora", "fr": "ff_siwis",
        "it": "if_sara", "pt-br": "pf_dora",
    }
    LANG_DETECT_MAP = {
        "en": "en-us", "es": "es", "fr": "fr",
        "it": "it", "pt": "pt-br",
    }

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self._pipelines = {}
        if KOKORO_AVAILABLE:
            print("[TTS Engine] Kokoro model ready for multilingual generation.")
        else:
            print("[TTS Engine] Warning: Kokoro or langdetect not installed. TTS will return empty audio.")

    def _get_pipeline(self, kokoro_code: str) -> Optional['KPipeline']:
        if not KOKORO_AVAILABLE:
            return None
        if kokoro_code not in self._pipelines:
            self._pipelines[kokoro_code] = KPipeline(lang_code=kokoro_code)
        return self._pipelines[kokoro_code]

    def detect_language(self, text: str) -> str:
        if not KOKORO_AVAILABLE:
            return "en-us"
        try:
            lang = detect(text)
            return self.LANG_DETECT_MAP.get(lang, "en-us")
        except:
            return "en-us"

    def speak_to_bytes(self, text: str, language: Optional[str] = None, speed: float = 1.0) -> bytes:
        """
        Generates TTS audio and returns it as a valid WAV byte stream.
        """
        if not KOKORO_AVAILABLE:
            raise RuntimeError("TTS dependencies (kokoro, langdetect) are not installed.")

        lang = language or self.detect_language(text)
        if lang not in self.LANG_CODES:
            lang = "en-us"

        kokoro_code = self.LANG_CODES[lang]
        voice = self.DEFAULT_VOICES[lang]
        pipeline = self._get_pipeline(kokoro_code)

        chunks = []
        # Kokoro pipeline yields (graphemes, phonemes, audio_array)
        for _, _, audio in pipeline(text, voice=voice, speed=speed):
            chunks.append(audio)

        if not chunks:
            raise RuntimeError("TTS generation resulted in empty audio.")

        full_audio = np.concatenate(chunks)
        
        # Write to in-memory bytes buffer
        buffer = io.BytesIO()
        sf.write(buffer, full_audio, 24000, format='WAV')
        buffer.seek(0)
        return buffer.read()

# Global Singleton singleton
_tts_engine = None

def get_tts_engine() -> MultilingualTTSEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = MultilingualTTSEngine()
    return _tts_engine
