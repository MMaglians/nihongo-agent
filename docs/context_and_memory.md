# Context window vs memory: a decision memo

## The question
What should an assistant see in every model call, and what should it store and fetch only
when needed? Every token in the context window is paid on every call and can distract the
model; everything kept outside must be retrieved at the right moment, or it is useless.

## Four places for information
| Where | Lifetime | Example in nihongo-agent | Cost |
|---|---|---|---|
| System prompt | always | tutor rules, citation rules | tokens on every call |
| Conversation history (checkpointer) | one thread | the previous turns | grows with the conversation |
| Retrieval (RAG) | one question | top-4 chunks of my notes | 1 embedding + chunk tokens |
| Long-term store (database) | across sessions | quiz progress in SQLite | a tool call, only when needed |

## Rules I used
1. Only what every turn needs goes in the prompt; everything else is fetched when the
   question needs it.
2. Retrieved chunks enter the context for the current turn only and are never written to the
   history: otherwise every later call would pay for them again.
3. Facts that must be exact and must survive sessions (was the quiz answer right?) are decided
   by code and stored in a database, not left to the model's memory of the conversation.

## Evidence from my evaluation (28 questions, 2026-11-06)
- Deciding where to look costs a call: the router raised model calls from 1.80 to 2.61 per
  question and the cost from 0.00040 $ to 0.00061 $ (about +50%), with no regression on the
  20 questions shared with v0.
- Retrieval is only as good as the decision to use it: when a question named my notes, it was
  answered from them (3/3) and absent topics were refused (2/2); the 3 questions that did not
  name the notes were sent to the dictionary instead.
- Keeping chunks out of the history kept the average input at 1,242 tokens per question.

## Recommendation for a client ("we want the assistant to remember our customers")
1. Store a small set of structured facts per customer (preferences, open requests), not whole
   transcripts, and only with a lawful basis under the GDPR: clear purpose, data minimisation,
   a retention period, and a way to see and delete what is stored.
2. Fetch those facts when a request needs them, through a tool or a retrieval step, and keep
   the conversation history short (recent turns only, or a summary).
3. Decide explicitly when to look things up: always (more reliable, one more call per turn) or
   only when the user refers to past information (cheaper, but depends on wording). Measure
   both on real follow-up questions before choosing.
4. Track the metrics that matter: correct use of memory, invented facts, cost and latency per turn.

## Risks
- Personal data in memory: a leak or a wrong retrieval exposes it to the wrong person.
- Memory can be wrong: my own notes contained mistakes (4 found in 20 pages) and the assistant
  repeats what it retrieves, so stored facts need review and a way to be corrected.
- Cost and noise grow with the history if nothing is trimmed or summarised.