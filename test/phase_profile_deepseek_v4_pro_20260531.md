# Phase Runtime Profile

- Generated: **2026-05-31 19:18:45**
- Run directory: `test/profile_runs/pro_20260531/20260531_191605`
- Scope: Phase B, Phase C, and Phase D on 5 fixed questions.
- Phase A is treated as completed and is not rerun by default.

## Summary

| Phase | Total | Main Components |
| --- | ---: | --- |
| Phase B | 20.672s | retriever_init=19.896s, 5_queries=0.776s |
| Phase C | 62.930s | provider=anthropic model=deepseek-v4-pro, prompt_build=0.000s, model_calls=62.930s |
| Phase D | 70.274s | api_init=0.004s, 5_api_posts=70.270s |
| Phase E | Not profiled | Deployment/pilot workflow has no local executable phase in this repo. |


## Phase B Details

- Chunks loaded: **401**
- Embedding backend: **sentence-transformers**
- Mean query time: **0.155s**
- Median query time: **0.143s**
- Slowest query time: **0.214s**

| Question | Retrieval | Answerability | Total | Status | Top Evidence |
| --- | ---: | ---: | ---: | --- | --- |
| What is convex hull? | 0.214s | 0.000s | 0.214s | `answerable` | `high_throughput/thermodynamics.md` `1.100` |
| How is Materials Project used in high-throughput screening? | 0.139s | 0.000s | 0.139s | `answerable` | `high_throughput/codes.md` `1.400` |
| What is the difference between molecular dynamics and Monte Carlo? | 0.143s | 0.000s | 0.143s | `answerable` | `models_and_theories_II/monte_carlo.md` `1.349` |
| When is assignment 1 due? | 0.134s | 0.000s | 0.134s | `needs_time_context` | `calendar.md` `1.250` |
| Tell me about models | 0.146s | 0.000s | 0.146s | `needs_clarification` | `models_and_theories_I/modelling.md` `0.748` |

## Phase C Details

- Provider/model: **anthropic / deepseek-v4-pro**
- Mean question time: **12.586s**
- Median question time: **10.845s**
- Slowest question time: **19.455s**

| Question | Prompt Build | Model Call | Total | OK | Status | Answer Chars |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| What is convex hull? | 0.000s | 13.173s | 13.173s | yes | `answerable` | 1241 |
| How is Materials Project used in high-throughput screening? | 0.000s | 19.455s | 19.455s | yes | `answerable` | 977 |
| What is the difference between molecular dynamics and Monte Carlo? | 0.000s | 10.326s | 10.326s | yes | `answerable` | 1406 |
| When is assignment 1 due? | 0.000s | 9.130s | 9.130s | yes | `needs_time_context` | 271 |
| Tell me about models | 0.000s | 10.845s | 10.845s | yes | `needs_clarification` | 645 |

## Phase D Details

- Mean API POST time: **14.054s**
- Median API POST time: **12.901s**
- Slowest API POST time: **20.496s**
- Note: Uses Flask test client against `/api/answer` with the current `.env` provider/model, matching the book widget request path.

| Question | API POST | HTTP | OK | Provider | Model | Status |
| --- | ---: | ---: | --- | --- | --- | --- |
| What is convex hull? | 20.496s | 200 | yes | `anthropic` | `deepseek-v4-pro` | `answerable` |
| How is Materials Project used in high-throughput screening? | 14.644s | 200 | yes | `anthropic` | `deepseek-v4-pro` | `answerable` |
| What is the difference between molecular dynamics and Monte Carlo? | 12.901s | 200 | yes | `anthropic` | `deepseek-v4-pro` | `answerable` |
| When is assignment 1 due? | 10.343s | 200 | yes | `anthropic` | `deepseek-v4-pro` | `needs_time_context` |
| Tell me about models | 11.886s | 200 | yes | `anthropic` | `deepseek-v4-pro` | `needs_clarification` |

## Notes

Phase B includes retriever initialization, which may include loading the sentence-transformers model and reading/building the embedding index cache.
Phase C isolates prompt construction and configured model-provider latency using the Phase B outputs.
Phase D measures the local `/api/answer` route with the current `.env` provider/model, so it includes route overhead, retriever setup, and real model latency.