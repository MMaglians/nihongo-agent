# Scope: nihongo-agent (pillar project)

## 1. Problem and user
I am a self-taught learner of Japanese and the only user of this tool. When I study, I search the web for readings, meanings and explanations, but jumping between sites is tiring and, as a learner, I cannot easily tell which answer to trust, so it slows me down instead of helping. Dictionary tools such as Jisho already handle lookup well, so the goal is not a better dictionary: it is a study companion that I can talk to in plain language, that quizzes me in the same conversation and that, in later versions, will use my own notes and my own progress (what I got wrong, what I have not seen yet). The first version answers vocabulary questions from the JMdict dictionary, shows which entry it used, and states explicitly when a word is not in the dictionary or when a piece of information comes from the model rather than from the dictionary. An agent fits better than a plain script because the model reads free-text requests and decides whether to look a word up, build a quiz or simply reply (a greeting needs no lookup), and how to handle a word that is missing.

## 2. Goal of the pillar
An agent for learning Japanese, built in versions: tool-calling loop (v0), routing,
RAG over personal notes and progress memory (v1), evaluation and security review,
cloud deployment, and a LoRA model compared with the API baseline.
Each version has a documented evaluation.

## 3. Scope of v0
In: a hand-written tool-calling loop on the Gemini API (max 6 steps per turn),
a dictionary tool (JMdict, common words) and a vocabulary quiz tool,
retries on server errors, JSONL execution traces, a command-line chat.
Out: memory across sessions, RAG, web UI, deployment, voice.

## 4. Roadmap
| Week | Version | Content |
|---|---|---|
| 5 | v1 | Routing, RAG over personal notes, progress memory (LangGraph) |
| 7 | | Evaluation report and threat model |
| 8-9 | | Azure deployment and demo video |
| 10 | | LoRA/QLoRA compared with the API baseline |
| After the 11-week plan | v2 (local only) | Optional private corpora (textbook PDF, other sources); never committed or deployed |

## 5. How success is measured (v0)
Primary metric: correct tool choice, computed automatically from the execution traces by comparing the tools called with the expected tool of each question.
Success criteria, fixed BEFORE running the evaluation. v0 passes only if all three hold:
- Correct tool choice: at least 18 of 20 questions.
- Correct answer (hand-labelled): at least 16 of 20 questions.
- Red line: zero invented dictionary entries on the 3 absent-word questions.
Alert thresholds (reported, investigated if exceeded, not pass/fail):
- Median time per question at most 10 s; mean steps at most 2.5.
- Pay-as-you-go equivalent cost at most 0.002 $ per question.
- No question reaches the 6-step limit; no API errors.
Labelling rules: [keep the four rules already written]
Confidence intervals: Wilson 95%. With n = 20 they are wide: the thresholds are go/no-go
decisions for v1, not statistical claims.

## 6. Risks and constraints
- Free-tier quotas and model names change; the model is set in `.env`.
- - Data use of prompts: under the official Gemini API Additional Terms (page last updated
2026-04-28, read on 2026-10-30), users in the EEA, Switzerland or the UK get the "Paid Services" data terms on all services, including unpaid quota: prompts and responses are not used to improve Google's products. Elsewhere the free tier may use submitted content to improve products, with human review. I am in Italy, so the first case applies; I still avoid sending sensitive or personal data. The same terms say that API clients made available to users in the EEA, Switzerland or the UK must use Paid Services, so a public demo for other people may need billing enabled; to be re-checked before the deployment (week 8).
- The dictionary is JMdict, common words only; licence CC BY-SA 4.0, attribution required, the file is not redistributed in this repository.
- One labeller who also wrote the questions; single run per question.

## 7. Out of scope
Not in v0: grammar answers, Italian-to-Japanese lookup (candidates for v1).
Planned after the 11-week plan: optional private corpora (e.g. a textbook PDF), local only;
they are never committed or deployed.
Grammar teaching as a curriculum, audio, handwriting, spaced-repetition scheduling.