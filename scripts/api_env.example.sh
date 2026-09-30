#!/usr/bin/env bash

# Copy this file to scripts/api_env.sh, fill in ONE of the provider blocks below,
# then load it with: source scripts/api_env.sh
# The local scripts/api_env.sh file is ignored by git.

# Option 1: Anthropic, or any server that speaks the Anthropic Messages API.
export LLM_PROVIDER="anthropic"
export ANTHROPIC_BASE_URL="https://claude.matsci.dev"
export ANTHROPIC_MODEL="deepseek-v4-flash"
export ANTHROPIC_AUTH_TOKEN="PASTE_YOUR_API_KEY_HERE"

# Option 2: OpenAI, or any OpenAI-compatible server (DeepSeek, OpenRouter, vLLM, Ollama, LM Studio, ...).
# export LLM_PROVIDER="openai"
# export OPENAI_BASE_URL="https://api.openai.com/v1"   # e.g. http://localhost:11434/v1 for Ollama
# export OPENAI_MODEL="gpt-4.1-mini"
# export OPENAI_API_KEY="PASTE_YOUR_API_KEY_HERE"      # local servers often need no key

# Option 3: Google Gemini.
# export LLM_PROVIDER="gemini"
# export GEMINI_MODEL="gemini-2.5-flash"
# export GEMINI_API_KEY="PASTE_YOUR_API_KEY_HERE"

# Optional: answer temperature for any provider (default 0.2). Use "none" for models
# that only accept their default, such as OpenAI's reasoning models.
# export LLM_TEMPERATURE="0.2"

# Do not let a stale key from the terminal override the value above.
unset ANTHROPIC_API_KEY

# Treat untouched placeholders as missing keys.
[[ "${ANTHROPIC_AUTH_TOKEN:-}" == "PASTE_YOUR_API_KEY_HERE" ]] && unset ANTHROPIC_AUTH_TOKEN
[[ "${OPENAI_API_KEY:-}" == "PASTE_YOUR_API_KEY_HERE" ]] && unset OPENAI_API_KEY
[[ "${GEMINI_API_KEY:-}" == "PASTE_YOUR_API_KEY_HERE" ]] && unset GEMINI_API_KEY

if [[ "${LLM_PROVIDER}" == "anthropic" && -z "${ANTHROPIC_AUTH_TOKEN:-}" ]] \
  || [[ "${LLM_PROVIDER}" == "gemini" && -z "${GEMINI_API_KEY:-}" ]] \
  || [[ "${LLM_PROVIDER}" == "openai" && -z "${OPENAI_API_KEY:-}" && "${OPENAI_BASE_URL:-}" == "https://api.openai.com/v1" ]]; then
  echo "Edit the API key for ${LLM_PROVIDER} in scripts/api_env.sh before starting the test site."
  return 1 2>/dev/null || exit 1
fi

echo "API environment loaded: ${LLM_PROVIDER}"
