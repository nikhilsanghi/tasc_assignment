"""LLM plumbing: client, structured-output helper, model/effort/thinking config, prompt loading (D-42)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import functools
import hashlib
import os

import anthropic
from pydantic import BaseModel

from core.paths import PROMPTS

MODEL_REASONING = os.environ.get("MODEL_REASONING", "claude-sonnet-5")
MODEL_FAST = os.environ.get("MODEL_FAST", "claude-sonnet-5")

EFFORT = {"compiler": "medium", "analyst": "low", "reranker": "medium", "judge": "medium"}
MAX_TOKENS = {"compiler": 4000, "analyst": 2500, "reranker": 3000, "judge": 2000}
THINKING = {"compiler": None, "analyst": {"type": "disabled"}, "reranker": None, "judge": None}


class LLMRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"rate limited, retry after {retry_after}s")


class LLMOutputError(Exception):
    def __init__(self, stop_reason: str | None):
        self.stop_reason = stop_reason
        super().__init__(f"bad LLM output: stop_reason={stop_reason}")


@functools.lru_cache
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(timeout=30.0, max_retries=1)


@functools.lru_cache
def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


def prompt_hash(name: str) -> str:
    return hashlib.sha256((PROMPTS / f"{name}.md").read_bytes()).hexdigest()[:12]


def _usage_dict(usage) -> dict:
    return {
        "input_tokens": getattr(usage, "input_tokens", None) or 0,
        "output_tokens": getattr(usage, "output_tokens", None) or 0,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None) or 0,
    }


def call_structured(system_blocks: list[dict], user_text: str, schema: type[BaseModel],
                     stage: str, model: str | None = None) -> tuple[BaseModel, dict]:
    client = get_client()
    if stage == "analyst":
        client = client.with_options(timeout=25.0, max_retries=0)
    kwargs = {"thinking": THINKING[stage]} if THINKING[stage] else {}
    try:
        response = client.messages.parse(
            model=model or MODEL_REASONING,
            max_tokens=MAX_TOKENS[stage],
            system=system_blocks,
            messages=[{"role": "user", "content": user_text}],
            output_format=schema,
            output_config={"effort": EFFORT[stage]},
            **kwargs,
        )
    except anthropic.RateLimitError as e:
        retry_after = int(e.response.headers.get("retry-after", 5))
        raise LLMRateLimited(retry_after) from e
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise LLMOutputError(response.stop_reason)
    return response.parsed_output, _usage_dict(response.usage)
