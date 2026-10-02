from __future__ import annotations

import json
import re

import requests


class OllamaClient:
    def __init__(self, base_url: str, default_model: str, timeout: int = 180) -> None:
        self._base = base_url.rstrip("/")
        self.default_model = default_model
        self._timeout = timeout

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self._base}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self._base}/api/tags", timeout=3)
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat(self, prompt: str, model: str | None = None) -> tuple[dict, str]:
        """
        Send a prompt to Ollama via the chat endpoint.
        Returns (parsed_dict, raw_text).
        Raises on network/HTTP errors or unparseable JSON.
        """
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a JSON API. Output ONLY valid JSON — no markdown fences, "
                        "no preamble, no explanation, no trailing text. "
                        "Your entire response must start with { and end with }."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 3000,
            },
        }
        r = requests.post(f"{self._base}/api/chat", json=payload, timeout=self._timeout)
        r.raise_for_status()
        raw = r.json()["message"]["content"]

        # Free VRAM immediately after generation
        try:
            requests.post(
                f"{self._base}/api/chat",
                json={"model": model, "messages": [], "keep_alive": 0},
                timeout=10,
            )
        except Exception:
            pass

        return self._parse_json_response(raw), raw

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError("No valid JSON object found in model output", text, 0)
