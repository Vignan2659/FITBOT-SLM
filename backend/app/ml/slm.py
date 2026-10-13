"""Local FitBot SLM inference.

Loads the fine-tuned FitBot model (merged weights, created by scripts/setup_model.py) once at
startup. If no fine-tuned model is installed yet, it falls back to the base model
(Qwen3-4B-Instruct-2507) and reports `fine_tuned: false` via /health so it is always clear
which model produced an answer.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

log = logging.getLogger(__name__)


def pick_device(pref: str = "auto") -> str:
    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class FitBotSLM:
    def __init__(self, model_path: Path | str, base_model: str, device: str = "auto", max_new_tokens: int = 220,
                 repetition_penalty: float = 1.1, dtype_name: str = "auto"):
        self.device = pick_device(device)
        self.max_new_tokens = max_new_tokens
        self.repetition_penalty = repetition_penalty
        self.card = {}
        if isinstance(model_path, str):          # Hugging Face Hub repo id, e.g. "you/fitbot-qwen3-4b"
            self.fine_tuned = model_path != base_model
            self.source = model_path
            try:
                from huggingface_hub import hf_hub_download
                self.card = json.loads(Path(hf_hub_download(model_path, "fitbot_model_card.json")).read_text())
            except Exception as exc:  # card is optional
                log.info("No fitbot_model_card.json in %s (%s)", model_path, exc)
        else:
            self.fine_tuned = (model_path / "config.json").exists()
            self.source = str(model_path) if self.fine_tuned else base_model
            if not self.fine_tuned:
                log.warning("Fine-tuned model not found at %s - falling back to base model %s", model_path, base_model)
            card_path = model_path / "fitbot_model_card.json"
            if card_path.exists():
                self.card = json.loads(card_path.read_text())
        dtype = torch.float16 if self.device in ("cuda", "mps") else torch.float32
        if self.device == "cuda" and torch.cuda.is_bf16_supported():
            dtype = torch.bfloat16   # Qwen3 is trained in bf16; fp16 can overflow
        if dtype_name != "auto":     # FITBOT_DTYPE override, e.g. bfloat16 / float32 if answers come out garbled
            dtype = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}[dtype_name]
        self.dtype = str(dtype).replace("torch.", "")

        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(self.source)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(self.source, dtype=dtype).to(self.device).eval()
        self.model.generation_config.pad_token_id = self.tokenizer.pad_token_id
        self.load_seconds = round(time.time() - t0, 2)
        self.params_m = round(sum(p.numel() for p in self.model.parameters()) / 1e6, 1)
        self._lock = threading.Lock()   # one generation at a time on a single local device
        log.info("Loaded %s (%sM params) on %s in %.1fs", self.source, self.params_m, self.device, self.load_seconds)

    @torch.inference_mode()
    def generate(self, messages: list[dict], max_new_tokens: int | None = None,
                 avoid: list[str] | None = None) -> tuple[str, float]:
        """Greedy generation. `avoid` lists phrases the model must not produce (bad_words_ids)."""
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        enc = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)
        extra = {}
        if avoid:
            extra["bad_words_ids"] = [self.tokenizer(p, add_special_tokens=False)["input_ids"] for p in avoid]
        with self._lock:
            t0 = time.time()
            out = self.model.generate(**enc, max_new_tokens=max_new_tokens or self.max_new_tokens, do_sample=False,
                                      repetition_penalty=self.repetition_penalty, pad_token_id=self.tokenizer.pad_token_id, **extra)
            dt = time.time() - t0
        text = self.tokenizer.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        return text, dt

    def info(self) -> dict:
        return {"model": self.source, "fine_tuned": self.fine_tuned, "device": self.device, "dtype": self.dtype,
                "params_m": self.params_m, "load_seconds": self.load_seconds, "card": self.card}
