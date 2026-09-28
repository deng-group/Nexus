# Phase Runtime Profile

- Generated: **2026-05-31 19:19:58**
- Run directory: `test/profile_runs/flash_20260531/20260531_191854`
- Scope: Phase B, Phase C, and Phase D on 5 fixed questions.
- Phase A is treated as completed and is not rerun by default.

## Summary

| Phase | Total | Main Components |
| --- | ---: | --- |
| Phase B | 19.466s | retriever_init=18.758s, 5_queries=0.707s |
| Phase C | 16.797s | provider=anthropic model=deepseek-v4-flash, prompt_build=0.000s, model_calls=16.796s |
| Phase D | 22.596s | api_init=0.002s, 5_api_posts=22.595s |
| Phase E | Not profiled | Deployment/pilot workflow has no local executable phase in this repo. |


## Phase B Details

- Chunks loaded: **401**
- Embedding backend: **sentence-transformers**
- Mean query time: **0.141s**
- Median query time: **0.134s**
- Slowest query time: **0.174s**

| Question | Retrieval | Answerability | Total | Status | Top Evidence |
| --- | ---: | ---: | ---: | --- | --- |
| What is convex hull? | 0.174s | 0.000s | 0.174s | `answerable` | `high_throughput/thermodynamics.md` `1.100` |
| How is Materials Project used in high-throughput screening? | 0.134s | 0.000s | 0.134s | `answerable` | `high_throughput/codes.md` `1.400` |
| What is the difference between molecular dynamics and Monte Carlo? | 0.133s | 0.000s | 0.133s | `answerable` | `models_and_theories_II/monte_carlo.md` `1.349` |
| When is assignment 1 due? | 0.129s | 0.000s | 0.130s | `needs_time_context` | `calendar.md` `1.250` |
| Tell me about models | 0.137s | 0.000s | 0.137s | `needs_clarification` | `models_and_theories_I/modelling.md` `0.748` |

## Phase C Details

- Provider/model: **anthropic / deepseek-v4-flash**
- Mean question time: **3.359s**
- Median question time: **3.527s**
- Slowest question time: **4.889s**

| Question | Prompt Build | Model Call | Total | OK | Status | Answer Chars |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| What is convex hull? | 0.000s | 3.527s | 3.527s | yes | `answerable` | 1134 |
| How is Materials Project used in high-throughput screening? | 0.000s | 2.059s | 2.059s | yes | `answerable` | 527 |
| What is the difference between molecular dynamics and Monte Carlo? | 0.000s | 4.889s | 4.889s | yes | `answerable` | 1459 |
| When is assignment 1 due? | 0.000s | 2.661s | 2.661s | yes | `needs_time_context` | 419 |
| Tell me about models | 0.000s | 3.660s | 3.660s | yes | `needs_clarification` | 797 |

## Phase D Details

- Mean API POST time: **4.519s**
- Median API POST time: **4.267s**
- Slowest API POST time: **6.258s**
- Note: Uses Flask test client against `/api/answer` with the current `.env` provider/model, matching the book widget request path.

| Question | API POST | HTTP | OK | Provider | Model | Status |
| --- | ---: | ---: | --- | --- | --- | --- |
| What is convex hull? | 3.056s | 200 | yes | `anthropic` | `deepseek-v4-flash` | `answerable` |
| How is Materials Project used in high-throughput screening? | 6.258s | 200 | yes | `anthropic` | `deepseek-v4-flash` | `answerable` |
| What is the difference between molecular dynamics and Monte Carlo? | 5.462s | 200 | yes | `anthropic` | `deepseek-v4-flash` | `answerable` |
| When is assignment 1 due? | 3.551s | 200 | yes | `anthropic` | `deepseek-v4-flash` | `needs_time_context` |
| Tell me about models | 4.267s | 200 | yes | `anthropic` | `deepseek-v4-flash` | `needs_clarification` |

## Notes

Phase B includes retriever initialization, which may include loading the sentence-transformers model and reading/building the embedding index cache.
Phase C isolates prompt construction and configured model-provider latency using the Phase B outputs.
Phase D measures the local `/api/answer` route with the current `.env` provider/model, so it includes route overhead, retriever setup, and real model latency.