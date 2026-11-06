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