<p align="center">
  <a href="https://github.com/deng-group/Nexus"><img src="docs/assets/logo/nexus_logo.svg" width="520" alt="Nexus: course knowledge graph and AI learning agent"></a>
</p>

<p align="center">
  <a href="https://mle4217-5219.matsci.dev/"><img src="https://img.shields.io/badge/example%20course-MLE4217%2F5219-2563eb" alt="Example course: MLE4217/5219"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/backend-Flask-000000?logo=flask&logoColor=white" alt="Flask backend">
  <img src="https://img.shields.io/badge/LLM-any%20API%20provider-d97706" alt="LLM: any API provider">
</p>

**Nexus** turns a set of course materials into an **interactive knowledge graph** and a **course-grounded AI learning agent**.
Students explore the curriculum as a network of chapters and concepts instead of a linear table of contents, click any node to
get an explanation that is backed only by the course's own materials, and jump straight to the page the answer came from.

Nexus was built for the NUS course [MLE4217/5219 Materials Informatics](https://mle4217-5219.matsci.dev/), whose
public course book is the example knowledge base used throughout this repository. The workflow itself is course-agnostic:
point the extraction step at any Markdown/Jupyter-based course site and the same graph builder, retrieval pipeline, and agent apply
without changing the code.

- [**Live example course**](https://mle4217-5219.matsci.dev/) (the source material Nexus was developed against)
- [**Developer notes**](README_DEVELOPERS.md) · [**Student-facing usage notes**](README_STUDENTS.md) · [**Product plan**](nexus/PROJECT_PLAN.md)

## How it works

<p align="center">
  <img src="docs/assets/nexus_workflow.png" width="100%" alt="Nexus workflow: course materials are extracted and chunked, feed a retrieval-augmented generation pipeline and an LLM, and surface as an interactive knowledge graph and an AI learning agent">
</p>

The pipeline runs in four stages, and two products branch off it:

1. **Course materials.** The input is the source of an existing course website: MyST/Markdown pages, Jupyter notebooks, the syllabus, and the calendar.
2. **Content extraction and chunking.** `backend/scripts/phase_a/extract_content.py` parses the source into chunk records with metadata
   (module, page, section, code vs. prose, temporal context). A small concept taxonomy tags each chunk with the course concepts it covers.
   ➜ **Product 1, the interactive knowledge graph**, is built deterministically from these chunks: chapters and concepts become nodes, and an
   edge is drawn only when the two nodes co-occur in the course materials.
3. **Retrieval-augmented generation (RAG).** A student question (plus the currently selected graph node as context) is answered by hybrid
   retrieval, BM25 lexical search fused with sentence-transformer embeddings, followed by an **answerability gate** that decides whether the
   retrieved evidence is strong enough to answer at all.
4. **Large language model.** Only when the gate passes is a prompt assembled from the retrieved chunks and sent to the configured model provider.
   Any Anthropic-compatible, OpenAI, or Gemini endpoint works; no fine-tuning or local GPU deployment is required.
   ➜ **Product 2, the AI learning agent**, streams the answer back with the course sources it used, each linked to the exact course page.

## Demo

### 1. Interactive knowledge graph

Nodes are **chapters** (blue) and **concepts** (orange). Start by clicking any node, filtering with the legend, or searching for a topic.
Selecting a chapter reveals the concepts it covers while keeping the other chapters visible, so shared concepts across chapters stand out.
Selecting a concept reveals every chapter in which it appears.

<p align="center">
  <img src="docs/assets/demo/knowledge_graph_demo.gif" width="100%" alt="Screen recording: exploring the Nexus knowledge graph by clicking nodes, using the legend, and searching">
</p>

<p align="center"><sub>Full-resolution recording: <a href="docs/assets/demo/knowledge_graph_demo.mp4">knowledge_graph_demo.mp4</a></sub></p>

### 2. AI learning agent

With a node selected, students can press **Explain**, pick a generated example question, ask a follow-up in the same session, and open the
cited course page directly from the answer. The agent answers using only the provided course evidence and says so explicitly when the
evidence is insufficient, ambiguous, time-dependent, or out of scope.

<p align="center">
  <img src="docs/assets/demo/ai_learning_agent_demo.gif" width="100%" alt="Screen recording: asking the Nexus AI learning agent to explain a selected node, following up, and opening the cited course page">
</p>

<p align="center"><sub>Full-resolution recording: <a href="docs/assets/demo/ai_learning_agent_demo.mp4">ai_learning_agent_demo.mp4</a></sub></p>

## Key features

**For students**

- **Exploration and explanation.** Navigate the course by curiosity, see how concepts connect across chapters, and ask for an explanation
  of any node within the current learning context.
- **Self-testing with visible boundaries.** Example questions, follow-up dialogue, and linked course sources support independent study,
  and the agent states explicitly when the course evidence is insufficient or the question is out of scope.

**For instructors**

- **Transferable framework.** Build the graph and the agent from your own teaching materials using the same extraction, retrieval, and
  evidence pipeline; the course-specific inputs are the content and a small concept taxonomy.
- **Lightweight and private.** Evidence-gated answers with minimal context sharing protect course data, and any LLM API provider works,
  so there is no costly local deployment or fine-tuning.
- **Control over answer policy.** The answerability gate, prompt, and evaluation sets let you decide what the agent may answer and verify it
  before students use it.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/app/` | Retriever, answerability gate, prompt builder, and answer generator (the RAG pipeline). |
| `backend/scripts/phase_a/` | Course content extraction and chunk-level knowledge-graph construction. |
| `backend/scripts/` | Query, prompt, answer, evaluation, profiling, and API-check command-line tools. |
| `nexus/` | The Nexus web app: Flask server (`app.py`), browser interface (`dist/`), graph builder and validator (`graph/`), generated graph (`data/`). |
| `web_app/` | Minimal chat window and the widget embedded in the course website. |
| `data/phase_a/` | Extracted chunk records and the chunk-level knowledge graph for the example course. |
| `test/` | Evaluation sets, reports, and the streaming test. |
| `deploy/` | Nginx, systemd, and sync scripts for hosting the API next to a static course site. |
| `docs/` | Figures, logo, demo recordings, and Phase A documentation. |

## Installation

Nexus requires Python 3.10 or newer.

```bash
git clone https://github.com/deng-group/Nexus.git
cd Nexus
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The first retrieval run downloads the sentence-transformer embedding model used for semantic search.

### Configure a model provider

Copy the safe template to the git-ignored local file, edit the endpoint, model, and key, then load it into the shell:

```bash
cp scripts/api_env.example.sh scripts/api_env.sh
source scripts/api_env.sh
python backend/scripts/check_api.py   # verifies endpoint, model, and key without printing the token
```

`scripts/api_env.sh` sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, and `ANTHROPIC_AUTH_TOKEN` for an Anthropic-compatible endpoint.
OpenAI (`OPENAI_API_KEY`, `OPENAI_MODEL`) and Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`) are supported through the same mechanism.
A small, inexpensive model is sufficient for the current workflow because the pipeline supplies the course evidence explicitly.

## Quick start

### Run Nexus on the example course

The repository ships with the extracted chunks and the generated graph for MLE4217/5219, so the app runs out of the box:

```bash
source scripts/api_env.sh
./scripts/start_nexus_test.sh          # checks the API, starts http://127.0.0.1:5057/, opens a browser
```

Add `--no-browser` to start the server only. Press `Ctrl+C` to stop.

### Try the pipeline from the command line

```bash
python backend/scripts/query.py  "What is convex hull?"                 # retrieval + answerability decision
python backend/scripts/answer.py "How is Materials Project data used to train MACE potentials?"
python backend/scripts/evaluate.py                                        # retrieval/answerability evaluation set
```

## Apply Nexus to your own course

Nexus needs a course source that is a folder of Markdown/MyST pages and Jupyter notebooks (a Jupyter Book or MyST site is the
intended shape). The steps are:

1. **Extract and chunk** the course content:

   ```bash
   python backend/scripts/phase_a/extract_content.py --repo /path/to/your_course_book --output data/phase_a/course_chunks.jsonl
   ```

2. **Describe the concepts** you want students to see as graph nodes in `nexus/graph/concept_taxonomy.json`
   (chapter list, concept names, aliases). This file is the only course-specific input besides the content itself.

3. **Build and validate the graph**:

   ```bash
   python nexus/graph/build_graph.py
   python nexus/graph/validate_graph.py
   ```

   The builder is deterministic: the same chunks and taxonomy always produce the same node IDs, edges, and ordering.

4. **Point source links at your site** by setting the course-site base URL in `nexus/app.py`, so cited sources open the correct page.

5. **Adapt the evaluation set** in `test/eval_set.json` to questions from your course and rerun `backend/scripts/evaluate.py`
   to confirm that retrieval and the answerability gate behave as intended before exposing the agent to students.

6. **Deploy** following [`deploy/DEPLOYMENT.md`](deploy/DEPLOYMENT.md), which hosts the static course site and the API behind one Nginx server.
   To embed the agent as a widget in the course website instead of (or in addition to) the standalone graph app, see the widget notes in
   [`README_DEVELOPERS.md`](README_DEVELOPERS.md).

## Evaluation

`test/` contains three evaluation layers that can be run without and with a live model:

| Script | What it checks | Model call |
| --- | --- | --- |
| `backend/scripts/evaluate.py` | Retrieval ranking and answerability status on `test/eval_set.json`. | No |
| `backend/scripts/evaluate_llm.py` | Prompt packaging, citations, and short-memory follow-ups with the `dry_run` provider. | No |
| `backend/scripts/evaluate_llm_real.py` | End-to-end answer quality for manual review, with retry and model fallback. | Yes |

Each run writes a current report and a timestamped copy under `test/`. See [`test/README.md`](test/README.md) for details.

## Citation and acknowledgements

Nexus is developed by the [Deng group](https://github.com/deng-group) at the Department of Materials Science and Engineering,
National University of Singapore, as part of an educational-technology project for MLE4217/5219 Materials Informatics.
If you use Nexus or adapt the workflow for your own course, please cite this repository:

```bibtex
@software{nexus2026,
  author = {Deng, Zeyu and contributors},
  title  = {Nexus: an interactive course knowledge graph and AI learning agent},
  year   = {2026},
  url    = {https://github.com/deng-group/Nexus}
}
```

