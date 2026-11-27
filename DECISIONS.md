# Architecture decisions

## 1. Hand-written loop, no framework
Decision: the agent loop is ~80 lines of plain Python. Why: to understand and control every
step (history, tool execution, stop conditions). A graph framework comes in v1.

## 2. Manual function calling
Decision: `generate_content` with automatic function calling disabled. Why: the loop, the
traces and the step limit are explicit; the model requests, the code executes.

## 3. Model: gemini-3.5-flash-lite, set in .env
Decision: a Flash-Lite model. Why: it is the lightweight option and it has a free tier (Google
pricing page, 2026-10-30), which fits the zero-budget constraint. The exact free-tier quotas are per project, change often and are shown in Google AI Studio, so they are not hard-coded anywhere in the repository. Consequence: model names are deprecated and replaced regularly, so the model is configurable through `.env`.

## 4. Step limit of 6 per turn
Decision: max 6 model calls per user message. Why: it protects quota and cost from loops. A
typical question needs a tool call and a final answer (2-3 model calls), so 6 leaves a margin;
the evaluation reports the measured mean. The ReAct paper (Yao et al., 2023, section 3.2) also
caps steps in its question-answering experiments (7 for HotpotQA, 5 for FEVER), because more
steps did not improve performance. The number 6 here is my own choice, not derived from the paper.

## 5. Errors as observations, infrastructure errors retried
Decision: a failing tool returns an error object to the model; 5xx API errors are retried
with exponential backoff; 4xx (e.g. quota) are not. Why: the model can recover from a tool
error, but cannot fix a server outage.

## 6. JMdict common-only, downloaded on demand
Decision: the dictionary is not committed. Why: licence CC BY-SA 4.0 with attribution, and
the file changes weekly. Consequence: a fetch script and an acknowledgements section.

## 7. History in memory only
Decision: no persistence in v0. Why: persistent memory is the subject of v1.

## 8. Small hand-labelled evaluation first
Decision: 20 questions, Wilson intervals, criteria and targets written before the run.
Limits: one labeller, single run, single-turn. Next: bootstrap and paired tests (week 7).

## 9. LangGraph for v1, the v0 loop kept as baseline
Decision: v1 is a LangGraph state graph (router, tool loop, retrieval); `agent.py` and the v0
tool declarations are unchanged. Why: explicit control flow, per-thread checkpoints, and an
honest paired comparison with v0 on the same questions.

## 10. A router with structured output
Decision: one extra model call classifies each message (use tools / retrieve / answer) with a
Pydantic schema; on invalid output it falls back to the tool branch. It also sees the last
tutor message (max 300 characters), so a bare "B" is read as a quiz answer.
Cost: one more call per turn (see the evaluation).

## 11. Retrieved notes are sent, not stored
Decision: retrieved chunks enter the context window only for the current turn and are never
written to the conversation history. Why: the history does not fill up with repeated chunks.

## 12. RAG with Gemini embeddings and numpy
Decision: gemini-embedding-001 at 768 dimensions, normalised vectors, cosine similarity with
numpy, top 4; chunks split by Markdown headings (max 1000 characters); a SHA-256 fingerprint
rebuilds the index only when notes or model change. Why: a few hundred chunks do not need FAISS.

## 13. Handwritten notes: transcribe once, review by hand, index only reviewed pages
Decision: Goodnotes PDF split into 5-page blocks, transcribed by Gemini with structured output
(Markdown + list of doubts), never auto-corrected; only pages I reviewed are indexed.
Why: a misread word would become a "fact" of my notes. Notes, PDFs and transcripts are private
and never committed. Course material (Marugoto) is used only as a personal reference, not indexed:
its terms allow personal use only.

## 14. Progress memory in SQLite, quiz checked by code
Decision: quiz questions are stored as pending; `check_answer` compares the letter with the
stored one and records the result; words wrong more often than right are offered for review.
Why: the model no longer decides whether an answer is correct; progress survives sessions.
LangGraph's in-memory store would be lost on exit.

## 15. Private evaluation results, public redacted copy
Decision: full v1 results stay in `data/` (ignored); `eval/results_v1.json` replaces answers to notes questions with a placeholder.


## 16. An LLM judge validated against my labels before any use
Decision: the judge applies the same rules I used for hand labelling, gives a binary verdict with the reasoning first, sees only the evidence the agent had, and the answer under review is fenced and marked as text to evaluate, not instructions. It runs on a different model from the generator. Unreadable verdicts are kept as missing, not counted as wrong.
Why: a judge is a measuring instrument with known biases (position, length, self-preference) and must be calibrated on labels it has not seen. Agreement is reported with Cohen's kappa and its interval, and with the direction of the disagreements, because a judge that is more lenient than the human is the dangerous case.

## 17. Azure services through local emulators, no cloud account
Decision: Blob Storage and Cosmos DB run as the official Microsoft emulators in Docker; no Azure
subscription was created. Why: the free account needs a credit card and identity data that I chose
not to provide, the Learn sandbox is no longer available, and free trials have no quota for Azure
OpenAI models. The emulators use the same SDKs and protocols, so the code is the same; what they do
not cover (authentication, RBAC, latency, cost) is stated as a limitation and replaced by a design
and a cost estimate.

## 18. Cosmos DB for NoSQL instead of Azure AI Search
Decision: the note vectors live in a Cosmos DB container (vector policy, cosine, DiskANN index).
Why: Cosmos DB has a local emulator with vector search, and in the target architecture it can also
hold the quiz progress, so one service replaces SQLite and the vector file. Trade-off: no hybrid
BM25 + vector ranking or semantic ranker, which AI Search offers; with 9 chunks this does not matter,
with a large document corpus AI Search would be the better fit.

## 19. Pluggable notes index and secrets, chosen by environment
Decision: `NOTES_BACKEND` (local or cosmos) and `SECRETS_BACKEND` (env or keyvault) select the
implementation; both default to the previous behaviour. Why: the graph depends on an interface
(`search()`, `get_secret()`), not on a service, so the same code runs on my PC, in Compose and in
the cloud. The Key Vault provider is tested only with a fake client; its SDKs are not installed.

## 20. One image, configuration at runtime
Decision: a slim, non-root image built from `uv.lock` with `--locked`; dependencies in a separate
layer; `.env`, notes and data excluded by `.dockerignore` and checked by tests. Why: the same image
can run anywhere, a rebuild after a code change takes seconds, and a published image cannot leak my
key or my notes.

## 21. Endpoint discovery off for the emulator
Decision: the Cosmos client is created with `enable_endpoint_discovery=False` (setting
`COSMOS_ENDPOINT_DISCOVERY`). Why: the emulator advertises `localhost`, which inside Compose points
to the agent's own container; with discovery off the SDK always uses `COSMOS_ENDPOINT`. A multi-region
account would turn it back on.

## 22. Backend comparison in the same session, interleaved and blind
Decision: the two backends answer the same 8 questions alternately in one session; the answers are
shuffled before labelling. Why: comparing with the v1 run of 2026-11-06 would mix the backend with
the chunking fix, the day and possible model drift; interleaving limits drift and blind labelling
limits my own bias. Consequence: the result can show a regression, not prove equivalence; identical
retrieved chunks are the main evidence.

## 23. Cost model with explicit assumptions, prices outside the code
Decision: `scripts/estimate_costs.py` computes the monthly cost from `docs/cost_inputs.json`, where
every price has a source and a date and every assumption is marked as measured or assumed; the
code refuses to run with a missing price. Why: prices change and some were read from secondary
sources; the reader can check and update them without touching code, and a sensitivity run shows
which assumptions matter.