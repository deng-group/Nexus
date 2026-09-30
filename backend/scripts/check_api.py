#!/usr/bin/env python3
"""Verify the configured LLM provider with one tiny request, without printing credentials."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.answer_generator import (
    default_model_name,
    default_provider_name,
    load_env_file,
    provider_from_name,
)


def main() -> None:
    load_env_file(REPO_ROOT / ".env")
    try:
        provider_name = default_provider_name()
    except ValueError as exc:
        raise SystemExit(f"API check failed: {exc}") from None
    if provider_name == "dry_run":
        raise SystemExit(
            "API check failed: no LLM provider is configured.\n"
            "Run `source scripts/api_env.sh` (copy it from scripts/api_env.example.sh first) or fill in .env."
        )

    model = default_model_name(provider_name)
    provider = provider_from_name(provider_name, model=model)
    prompt_package = {
        "messages": [
            {"role": "system", "content": "This is a connectivity check."},
            {"role": "user", "content": "Reply with OK."},
        ],
        "evidence": [],
    }
    try:
        result = provider.generate(prompt_package)
    except (RuntimeError, OSError, ValueError) as exc:
        raise SystemExit(f"API check failed ({provider_name} / {model}): {str(exc)[:500]}") from None
    if not str(result.get("answer") or "").strip():
        raise SystemExit("API check failed: the endpoint returned no text content.")
    print(f"API check passed: {provider_name} / {model}")


if __name__ == "__main__":
    main()
