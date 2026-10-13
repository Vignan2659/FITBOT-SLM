"""Neural voice-over with Kokoro-82M (Apache-2.0, runs offline). Run with the separate TTS environment:

    .venv-tts/bin/python tts_kokoro.py jobs.json      # jobs.json: [{"text": ..., "out": ".../x.wav"}, ...]

Writes 24 kHz mono 16-bit WAVs. voice.py calls this automatically when the environment exists.
"""
import json
import os
import re
import sys
import wave

import numpy as np
from kokoro import KPipeline

VOICE = os.environ.get("FITBOT_KOKORO_VOICE", "af_heart")
SPEED = float(os.environ.get("FITBOT_KOKORO_SPEED", "1.0"))

# brand / technical words -> explicit pronunciation (misaki inline phonemes) or plain spelling
FIX = [
    (r"\bFitBot\b", "[FitBot](/fˈɪtbˌɑt/)"),
    (r"\bVeltris\b", "[Veltris](/vˈɛltɹɪs/)"),
    (r"\bQwen\b", "[Qwen](/kwˈɛn/)"),
    (r"\bQ-LoRA\b", "[QLoRA](/kjˈu lˈɔɹə/)"),
    (r"\bU\.S\.D\.A\.", "U S D A"),
    (r"\bG\.P\.U\.", "G P U"),
]


def prep(text: str) -> str:
    for pat, rep in FIX:
        text = re.sub(pat, rep, text)
    return text


def main() -> None:
    jobs = json.load(open(sys.argv[1]))
    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    for j in jobs:
        chunks = [np.asarray(a, dtype=np.float32) for _, _, a in pipe(prep(j["text"]), voice=VOICE, speed=SPEED)]
        audio = np.concatenate(chunks) if chunks else np.zeros(2400, dtype=np.float32)
        audio = audio / max(np.abs(audio).max(), 1e-6) * 0.95
        with wave.open(j["out"], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes((audio * 32767).astype(np.int16).tobytes())
        print("ok", os.path.basename(j["out"]), f"{len(audio) / 24000:.1f}s", flush=True)


if __name__ == "__main__":
    main()
