from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.llm.prompts import CATEGORIES, CATEGORY_PROMPT, SUMMARY_PROMPT

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails permanently."""


class GeminiClient:
    """Thin wrapper around google-generativeai with retry + JSON parsing."""

    def __init__(self) -> None:
        self.model_name = settings.GEMINI_MODEL
        self.api_key = settings.GEMINI_API_KEY
        self._model = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.api_key or self.api_key == "replace_me_with_your_google_ai_studio_key":
            raise LLMError("GEMINI_API_KEY is not configured.")
        import google.generativeai as genai  # local import to avoid boot cost

        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)
        return self._model

    @staticmethod
    def _strip_json(text: str) -> str:
        text = text.strip()
        # Remove ```json ... ``` fences if the model added them.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _generate(self, prompt: str) -> str:
        model = self._ensure_model()

        @retry(
            reraise=True,
            stop=stop_after_attempt(settings.GEMINI_MAX_RETRIES),
            wait=wait_exponential(
                multiplier=settings.GEMINI_RETRY_BASE_SECONDS, min=1, max=30
            ),
            retry=retry_if_exception_type(Exception),
        )
        def _call() -> str:
            resp = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            )
            text = getattr(resp, "text", None)
            if not text:
                raise LLMError("Empty response from Gemini")
            return text

        try:
            return _call()
        except RetryError as exc:  # pragma: no cover
            raise LLMError(f"Gemini retries exhausted: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Gemini call failed: {exc}") from exc

    # ---- Public API ----

    def categorize_batch(
        self, items: List[Dict[str, Any]]
    ) -> Optional[Dict[str, str]]:
        """
        items: [{txn_id, merchant, amount, currency, notes}, ...]
        returns: {txn_id: category} or None on failure.
        """
        if not items:
            return {}
        try:
            prompt = CATEGORY_PROMPT.format(
                categories=", ".join(CATEGORIES),
                items=json.dumps(items, ensure_ascii=False),
            )
            raw = self._generate(prompt)
            parsed = json.loads(self._strip_json(raw))
            out: Dict[str, str] = {}
            for row in parsed.get("results", []):
                tid = row.get("txn_id")
                cat = row.get("category")
                if tid and cat in CATEGORIES:
                    out[tid] = cat
                elif tid:
                    out[tid] = "Other"
            return out
        except (LLMError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Gemini categorize_batch failed: %s", exc)
            return None

    def summarize(self, stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            prompt = SUMMARY_PROMPT.format(
                stats=json.dumps(stats, ensure_ascii=False, default=str)
            )
            raw = self._generate(prompt)
            parsed = json.loads(self._strip_json(raw))
            return parsed
        except (LLMError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Gemini summarize failed: %s", exc)
            return None


def get_gemini_client() -> GeminiClient:
    return GeminiClient()
