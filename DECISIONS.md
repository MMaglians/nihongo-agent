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