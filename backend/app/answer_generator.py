#!/usr/bin/env python3
"""Phase C answer generation layer.

This module connects the query pipeline and prompt builder to a pluggable LLM
provider. The default provider is a dry-run provider so tests can run without
API keys or network access.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.prompt_builder import PromptBuilder
from backend.app.query_pipeline import QueryPipeline


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_TEMPERATURE = 0.2


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding existing environment."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def temperature_setting() -> dict:
    """Return the request's temperature field, read from `LLM_TEMPERATURE`.

    Defaults to 0.2 for focused, evidence-based answers. Set `LLM_TEMPERATURE=none`
    to leave the field out, for models that only accept their default temperature
    (for example OpenAI reasoning models).
    """
    raw = os.environ.get("LLM_TEMPERATURE", "").strip()
    if not raw:
        return {"temperature": DEFAULT_TEMPERATURE}
    if raw.lower() == "none":
        return {}
    try:
        return {"temperature": float(raw)}
    except ValueError:
        raise RuntimeError(f"LLM_TEMPERATURE must be a number or `none`, not `{raw}`.") from None


def _open(req: request.Request, label: str, timeout: int):
    """Open an HTTP request and turn transport failures into readable errors."""
    try:
        return request.urlopen(req, timeout=timeout)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{label} API error {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{label} API unreachable: {exc.reason}") from exc


def _iter_sse_data(response) -> Iterator[dict]:
    """Yield the JSON payloads of the `data:` lines in a server-sent event stream."""
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        yield json.loads(data)


class LLMProvider(Protocol):
    """Provider interface used by AnswerGenerator."""

    name: str

    def generate(self, prompt_package: dict) -> dict:
        """Generate an answer from a prompt package."""


@dataclass
class DryRunProvider:
    """Deterministic provider for local testing.

    It does not pretend to be an LLM. It returns a compact, policy-aware preview
    that lets us verify routing, evidence selection, citations, temporal context,
    and short-memory packaging.
    """

    name: str = "dry_run"

    def resolved_model(self) -> None:
        return None

    def generate(self, prompt_package: dict) -> dict:
        action = prompt_package["llm_action"]
        status = prompt_package["status"]
        evidence = prompt_package.get("evidence", [])
        citations = [item["chunk_id"] for item in evidence]

        if action == "generate_answer":
            lead = "Dry run answer preview: this question is ready for an LLM answer using the selected course evidence."
            if prompt_package["answer_policy"].get("requires_temporal_context"):
                lead += f" Temporal context required: {prompt_package['answer_policy']['temporal_context']}."
            if citations:
                lead += " Candidate citations: " + ", ".join(citations) + "."
        elif action == "ask_clarification":
            lead = "Dry run answer preview: ask the student to narrow the question before answering."
        elif action == "insufficient_evidence":
            lead = "Dry run answer preview: explain that the course evidence is insufficient for a verified answer."
        elif action == "refuse_or_fallback":
            lead = "Dry run answer preview: explain that the question appears outside the course scope."
        else:
            lead = f"Dry run answer preview: inspect status `{status}` before answering."

        return {
            "provider": self.name,
            "model": None,
            "answer": lead,
            "citations": citations,
            "raw_response": None,
        }

    def stream(self, prompt_package: dict) -> Iterator[str]:
        words = self.generate(prompt_package)["answer"].split(" ")
        for index, word in enumerate(words):
            yield word if index == 0 else f" {word}"


@dataclass
class OpenAICompatibleProvider:
    """OpenAI Chat Completions provider for OpenAI and any compatible endpoint.

    Works with any server that implements `POST {base_url}/chat/completions`,
    such as OpenAI, DeepSeek, OpenRouter, vLLM, Ollama, or LM Studio. Configure
    it with `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. The key is
    optional for custom base URLs, since local servers often need none.
    """

    model: str | None = None
    name: str = "openai"

    def resolved_model(self) -> str:
        return self.model or os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL

    def _request(self, prompt_package: dict, stream: bool) -> request.Request:
        base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).rstrip("/")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key and base_url == DEFAULT_OPENAI_BASE_URL:
            raise RuntimeError("Set OPENAI_API_KEY before using the OpenAI provider.")

        messages = prompt_package["messages"]
        payload = {
            "model": self.resolved_model(),
            **temperature_setting(),
            "messages": [
                {"role": "system", "content": messages[0]["content"]},
                {"role": "user", "content": messages[1]["content"]},
            ],
        }
        if stream:
            payload["stream"] = True
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    def generate(self, prompt_package: dict) -> dict:
        with _open(self._request(prompt_package, stream=False), "OpenAI-compatible", timeout=90) as response:
            raw = json.loads(response.read().decode("utf-8"))
        return {
            "provider": self.name,
            "model": self.resolved_model(),
            "answer": self._extract_text(raw),
            "citations": [item["chunk_id"] for item in prompt_package.get("evidence", [])],
            "raw_response": raw,
        }

    def stream(self, prompt_package: dict) -> Iterator[str]:
        """Yield text deltas from an OpenAI-compatible SSE response."""
        with _open(self._request(prompt_package, stream=True), "OpenAI-compatible", timeout=120) as response:
            for event_payload in _iter_sse_data(response):
                if event_payload.get("error"):
                    message = event_payload["error"].get("message", "Unknown streaming error")
                    raise RuntimeError(f"OpenAI-compatible API error: {message}")
                for choice in event_payload.get("choices", []):
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield text

    @staticmethod
    def _extract_text(raw: dict) -> str:
        parts = []
        for choice in raw.get("choices", []):
            text = (choice.get("message") or {}).get("content")
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        return json.dumps(raw, ensure_ascii=False)


@dataclass
class GeminiProvider:
    """Google Gemini REST provider using generateContent."""

    model: str | None = None
    name: str = "gemini"

    def resolved_model(self) -> str:
        return self.model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    def _request(self, prompt_package: dict, stream: bool) -> request.Request:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before using the Gemini provider.")

        messages = prompt_package["messages"]
        method = "streamGenerateContent?alt=sse" if stream else "generateContent"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.resolved_model()}:{method}"
        payload = {
            "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
            "generationConfig": temperature_setting(),
        }
        return request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

    def generate(self, prompt_package: dict) -> dict:
        with _open(self._request(prompt_package, stream=False), "Gemini", timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
        return {
            "provider": self.name,
            "model": self.resolved_model(),
            "answer": self._extract_text(raw),
            "citations": [item["chunk_id"] for item in prompt_package.get("evidence", [])],
            "raw_response": raw,
        }

    def stream(self, prompt_package: dict) -> Iterator[str]:
        """Yield text deltas from a Gemini SSE response."""
        with _open(self._request(prompt_package, stream=True), "Gemini", timeout=120) as response:
            for event_payload in _iter_sse_data(response):
                if event_payload.get("error"):
                    message = event_payload["error"].get("message", "Unknown streaming error")
                    raise RuntimeError(f"Gemini API error: {message}")
                for candidate in event_payload.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if part.get("text"):
                            yield part["text"]

    @staticmethod
    def _extract_text(raw: dict) -> str:
        parts = []
        for candidate in raw.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text = part.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        return json.dumps(raw, ensure_ascii=False)


@dataclass
class AnthropicProvider:
    """Anthropic-compatible Messages API provider."""

    model: str | None = None
    name: str = "anthropic"

    def resolved_model(self) -> str:
        return self.model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL

    def generate(self, prompt_package: dict) -> dict:
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
        model = self.model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
        if not token:
            raise RuntimeError("Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY before using the Anthropic provider.")

        messages = prompt_package["messages"]
        payload = {
            "model": model,
            "max_tokens": 2048,
            **temperature_setting(),
            "system": messages[0]["content"],
            "messages": [
                {
                    "role": "user",
                    "content": messages[1]["content"],
                }
            ],
        }
        # Keep credentials and request content out of the process command line,
        # where local process-inspection tools could otherwise reveal them.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as config:
            escaped_token = token.replace("\\", "\\\\").replace('"', '\\"')
            config.write(f'url = "{base_url}/v1/messages"\n')
            config.write('header = "content-type: application/json"\n')
            config.write('header = "anthropic-version: 2023-06-01"\n')
            config.write(f'header = "x-api-key: {escaped_token}"\n')
            config.write('request = "POST"\n')
            config.flush()
            completed = subprocess.run(
                [
                    "curl",
                    "-sS",
                    "--fail-with-body",
                    "--max-time",
                    "90",
                    "--config",
                    config.name,
                    "--data-binary",
                    "@-",
                ],
                input=json.dumps(payload),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        if completed.returncode != 0:
            body = (completed.stdout or completed.stderr).strip()
            raise RuntimeError(f"Anthropic API error via curl: {body}")
        raw = json.loads(completed.stdout)

        answer = self._extract_text(raw)
        return {
            "provider": self.name,
            "model": model,
            "answer": answer,
            "citations": [item["chunk_id"] for item in prompt_package.get("evidence", [])],
            "raw_response": raw,
        }

    def stream(self, prompt_package: dict) -> Iterator[str]:
        """Yield text deltas from an Anthropic-compatible SSE response."""
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
        if not token:
            raise RuntimeError("Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY before using the Anthropic provider.")

        messages = prompt_package["messages"]
        payload = {
            "model": self.resolved_model(),
            "max_tokens": 2048,
            **temperature_setting(),
            "stream": True,
            "system": messages[0]["content"],
            "messages": [{"role": "user", "content": messages[1]["content"]}],
        }

        process = None
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as config:
            escaped_token = token.replace("\\", "\\\\").replace('"', '\\"')
            config.write(f'url = "{base_url}/v1/messages"\n')
            config.write('header = "content-type: application/json"\n')
            config.write('header = "anthropic-version: 2023-06-01"\n')
            config.write(f'header = "x-api-key: {escaped_token}"\n')
            config.write('request = "POST"\n')
            config.flush()
            process = subprocess.Popen(
                [
                    "curl",
                    "-sS",
                    "--no-buffer",
                    "--fail-with-body",
                    "--max-time",
                    "120",
                    "--config",
                    config.name,
                    "--data-binary",
                    "@-",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(json.dumps(payload))
            process.stdin.close()
            non_event_output = []
            try:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        if line and not line.startswith("event:"):
                            non_event_output.append(line)
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    event_payload = json.loads(data)
                    if event_payload.get("type") == "error":
                        message = event_payload.get("error", {}).get("message", "Unknown streaming error")
                        raise RuntimeError(f"Anthropic API error: {message}")
                    if event_payload.get("type") != "content_block_delta":
                        continue
                    delta = event_payload.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
                return_code = process.wait()
                if return_code != 0:
                    assert process.stderr is not None
                    body = " ".join(non_event_output) or process.stderr.read().strip()
                    raise RuntimeError(f"Anthropic streaming API error via curl: {body}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

    @staticmethod
    def _extract_text(raw: dict) -> str:
        parts = []
        for item in raw.get("content", []):
            text = item.get("text")
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        return json.dumps(raw, ensure_ascii=False)


class AnswerGenerator:
    """End-to-end Phase C interface for one student question."""

    def __init__(
        self,
        pipeline: QueryPipeline | None = None,
        prompt_builder: PromptBuilder | None = None,
        provider: LLMProvider | None = None,
    ):
        self.pipeline = pipeline or QueryPipeline()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.provider = provider or DryRunProvider()

    def _prepare(
        self,
        query: str,
        short_memory: list[dict] | None = None,
        selected_context: list[str] | None = None,
    ) -> tuple[dict, dict]:
        memory = short_memory or []
        context = selected_context or []
        pipeline_kwargs = {"short_memory": memory}
        if context:
            pipeline_kwargs["context_terms"] = context
        pipeline_result = self.pipeline.ask(query, **pipeline_kwargs)
        prompt_package = self.prompt_builder.build(
            pipeline_result,
            short_memory=memory,
            selected_context=context,
        )
        return pipeline_result, prompt_package

    def answer(
        self,
        query: str,
        short_memory: list[dict] | None = None,
        selected_context: list[str] | None = None,
    ) -> dict:
        pipeline_result, prompt_package = self._prepare(query, short_memory, selected_context)
        if prompt_package["llm_action"] == "generate_answer":
            provider_result = self.provider.generate(prompt_package)
            sources = self._student_sources(prompt_package["evidence"])
        else:
            provider_result = {
                "provider": "course_policy",
                "model": None,
                "answer": self._policy_answer(prompt_package["llm_action"]),
                "citations": [],
                "raw_response": None,
            }
            sources = []
        answer = self._hide_internal_chunk_ids(provider_result["answer"], prompt_package["evidence"])

        return {
            "query": query,
            "status": prompt_package["status"],
            "llm_action": prompt_package["llm_action"],
            "next_action": pipeline_result["next_action"],
            "answer": answer,
            "citations": provider_result["citations"],
            "sources": sources,
            "provider": provider_result["provider"],
            "model": provider_result["model"],
            "confidence": pipeline_result["confidence"],
            "temporal_context": pipeline_result["temporal_context"],
            "short_memory": prompt_package["short_memory"],
            "evidence": prompt_package["evidence"],
            "prompt_package": prompt_package,
            "raw_response": provider_result["raw_response"],
        }

    def stream_answer(
        self,
        query: str,
        short_memory: list[dict] | None = None,
        selected_context: list[str] | None = None,
    ) -> Iterator[dict]:
        pipeline_result, prompt_package = self._prepare(query, short_memory, selected_context)
        should_generate = prompt_package["llm_action"] == "generate_answer"
        sources = self._student_sources(prompt_package["evidence"]) if should_generate else []
        resolve_model = getattr(self.provider, "resolved_model", None)
        model = (resolve_model() if callable(resolve_model) else getattr(self.provider, "model", None)) if should_generate else None
        provider_name = self.provider.name if should_generate else "course_policy"

        yield {
            "type": "start",
            "ok": True,
            "query": query,
            "status": prompt_package["status"],
            "llm_action": prompt_package["llm_action"],
            "provider": provider_name,
            "model": model,
            "confidence": pipeline_result["confidence"],
            "temporal_context": pipeline_result["temporal_context"],
            "sources": self._public_sources(sources),
        }

        if not should_generate:
            answer = self._policy_answer(prompt_package["llm_action"])
            yield {"type": "delta", "text": answer}
            yield {
                "type": "done",
                "ok": True,
                "answer": answer,
                "status": prompt_package["status"],
                "llm_action": prompt_package["llm_action"],
                "provider": provider_name,
                "model": None,
                "confidence": pipeline_result["confidence"],
                "temporal_context": pipeline_result["temporal_context"],
                "sources": [],
            }
            return

        stream = getattr(self.provider, "stream", None)
        if callable(stream):
            deltas = stream(prompt_package)
        else:
            # Providers without streaming still work; the answer arrives as one delta.
            deltas = iter([self.provider.generate(prompt_package)["answer"]])

        chunks = []
        for delta in deltas:
            if not delta:
                continue
            chunks.append(delta)
            yield {"type": "delta", "text": self._replace_chunk_ids(delta, prompt_package["evidence"])}

        if not chunks:
            raise RuntimeError("The model stream completed without returning answer text.")
        answer = self._hide_internal_chunk_ids("".join(chunks), prompt_package["evidence"])
        yield {
            "type": "done",
            "ok": True,
            "answer": answer,
            "status": prompt_package["status"],
            "llm_action": prompt_package["llm_action"],
            "provider": self.provider.name,
            "model": model,
            "confidence": pipeline_result["confidence"],
            "temporal_context": pipeline_result["temporal_context"],
            "sources": self._public_sources(sources),
        }

    @staticmethod
    def _policy_answer(action: str) -> str:
        if action == "ask_clarification":
            return "Please narrow the question to a specific course concept, chapter, task, or comparison."
        if action == "refuse_or_fallback":
            return "I don’t know based on the course materials. This question appears to be outside the scope of MLE4217/5219."
        return "I don’t know based on the available course materials. Try asking about a more specific course concept or chapter."

    @staticmethod
    def _student_sources(evidence: list[dict]) -> list[dict]:
        sources = []
        seen = set()
        for item in evidence:
            key = (item["title"], item["file_path"])
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "title": item["title"],
                    "file_path": item["file_path"],
                    "chunk_id": item["chunk_id"],
                    "score": item["score"],
                }
            )
        return sources

    @staticmethod
    def _public_sources(sources: list[dict]) -> list[dict]:
        return [
            {
                "title": source["title"],
                "file_path": source["file_path"],
                "score": source["score"],
            }
            for source in sources
        ]

    @staticmethod
    def _hide_internal_chunk_ids(answer: str, evidence: list[dict]) -> str:
        cleaned = AnswerGenerator._replace_chunk_ids(answer, evidence)
        cleaned = re.sub(r"\(\s*chunk_id\s*=\s*[^)]+\)", "", cleaned)
        cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
        return cleaned.strip()

    @staticmethod
    def _replace_chunk_ids(answer: str, evidence: list[dict]) -> str:
        cleaned = answer
        for item in evidence:
            replacement = f"{item['title']} ({item['file_path']})"
            cleaned = cleaned.replace(item["chunk_id"], replacement)
        return cleaned


PROVIDER_NAMES = ("dry_run", "anthropic", "openai", "gemini")


def provider_from_name(name: str, model: str | None = None) -> LLMProvider:
    if name == "dry_run":
        return DryRunProvider()
    if name == "openai":
        return OpenAICompatibleProvider(model=model)
    if name == "gemini":
        return GeminiProvider(model=model)
    if name == "anthropic":
        return AnthropicProvider(model=model)
    raise ValueError(f"Unknown provider: {name}")


def default_provider_name() -> str:
    """Pick the provider from `LLM_PROVIDER`, else from whichever credentials are set."""
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in PROVIDER_NAMES:
            raise ValueError(f"Unknown LLM_PROVIDER `{explicit}`; expected one of {', '.join(PROVIDER_NAMES)}.")
        return explicit
    if os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"):
        return "openai"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return "dry_run"


def default_model_name(provider: str) -> str | None:
    resolve_model = getattr(provider_from_name(provider), "resolved_model", None)
    return resolve_model() if callable(resolve_model) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an answer package for one query.")
    parser.add_argument("query")
    parser.add_argument("--provider", choices=PROVIDER_NAMES, default="dry_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-evidence", type=int, default=None)
    parser.add_argument("--evidence-threshold", type=float, default=0.60)
    parser.add_argument("--memory-json", type=Path, default=None)
    parser.add_argument("--include-prompt", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env_file)

    memory = []
    if args.memory_json:
        memory = json.loads(args.memory_json.read_text(encoding="utf-8"))

    generator = AnswerGenerator(
        pipeline=QueryPipeline(top_k=args.top_k),
        prompt_builder=PromptBuilder(
            max_evidence=args.max_evidence,
            evidence_score_threshold=args.evidence_threshold,
        ),
        provider=provider_from_name(args.provider, model=args.model),
    )
    try:
        result = generator.answer(args.query, short_memory=memory)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "provider": args.provider,
                    "model": args.model,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from exc
    if not args.include_prompt:
        result.pop("prompt_package", None)
        result.pop("raw_response", None)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
