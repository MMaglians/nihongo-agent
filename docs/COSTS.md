# Monthly cost of the target Azure architecture

**Question.** A language school asks: what would it cost per month to run this tutor on Azure for
one learner, a class of 30 and a school of 300, and what drives the cost?

**Scope.** The target architecture in the README (Container Apps, Cosmos DB serverless, Blob
Storage, Key Vault, container registry, Log Analytics) plus the Gemini API. Nothing was deployed:
this is an estimate from unit prices and usage assumptions.

## Method
Monthly cost = usage × unit price − free grants, per component. Usage per learner: 12 sessions a
month, 15 questions and 20 minutes per session. Inputs, sources and notes:
[cost_inputs.json](cost_inputs.json). Reproduce: `uv run python scripts/estimate_costs.py`.

| Input | Value | Type |
|---|---|---|
| Tokens per question (in / out) | 1,242 / 95 | measured (v1 evaluation, 28 questions) |
| Share of notes questions | 0.29 | from the test set (8 of 28) |
| Sessions, questions, minutes | 12 per month, 15, 20 | assumed |
| Replica size | 0.5 vCPU, 1 GiB | assumed |
| Sessions per replica | 1 (command-line chat) | design of today |
| RU per vector search | 50 | assumed, not measured (sensitivity x10) |
| Container Apps free grant | 180,000 vCPU-s, 360,000 GiB-s per month | verified, Azure pricing page |

Prices: read on 2026-11-27, **East US**, USD. Official Azure pricing pages render prices in the
browser and could not be read automatically, so most values come from Microsoft Learn or from
third parties quoting the Azure Retail Prices API; Log Analytics comes from a source to be
confirmed. The gemini-3.5-flash-lite price (0.30 / 2.50 $ per million tokens) was not found on
Google's pricing page on 2026-11-27 and comes from third parties; it matches the value read on
Google's page on 2026-10-30.

## Results (USD per month)
| Component | 1 learner | 30 learners | 300 learners |
|---|---|---|---|
| Container Apps | 0.00 | 1.08 | 59.40 |
| Cosmos DB | 0.01 | 0.04 | 0.25 |
| Blob Storage | 0.00 | 0.00 | 0.00 |
| Key Vault | 0.00 | 0.00 | 0.02 |
| Container registry (ACR Basic) | 5.01 | 5.01 | 5.01 |
| Log Analytics | 0.00 | 0.00 | 2.30 |
| Gemini API | 0.11 | 3.30 | 33.02 |
| **Total** | **5.13** | **9.43** | **100.00** |
| Per learner | 5.13 | 0.31 | 0.33 |

Sensitivity, RU per vector search x10: 5.14 / 9.65 / 102.17 — the weakest assumption does not
change the conclusions. What-if, an HTTP API serving 10 sessions per replica: 5.13 / 8.35 / 41.68.

## Reading the numbers
- **1 learner:** almost all of the cost is fixed (the registry). Compute stays inside the free grant
  (7,200 of 180,000 vCPU-seconds).
- **30 learners:** the model is the largest item; 0.00061 $ per question, as in the README.
- **300 learners:** Container Apps dominates because today's command-line chat needs one container
  per conversation. This is an architecture choice, not a property of the service.
- Cosmos DB, Blob Storage and Key Vault stay below 0.30 $ in every scenario.

## Recommendations
1. **Demo or single learner:** publish the image on GitHub Container Registry (free for public
   images) instead of Azure Container Registry: about 0.12 $ a month instead of 5.13 $.
2. **Before going beyond one class:** put an HTTP API in front of the agent so that one replica serves
   several sessions. At 300 learners this cuts the estimate from 100.00 $ to 41.68 $ (-58%), and the
   model becomes the main cost.
3. **Then optimise the model cost, measuring quality:** notes questions use about 1,630 input
   tokens against 1,242 on average, because the retrieved chunks enter the prompt; fewer or shorter
   chunks, or routing easy questions to a smaller model, are the next levers. Each change needs the
   evaluation re-run.
4. **Move quiz progress to Cosmos DB** before deploying: a container's disk is not persistent. The
   cost impact is already in the estimate (progress writes are counted in RU).
5. **For learners in the EU:** re-price in an EU region and review the data flows: notes and
   questions are sent to the Gemini API, outside Azure.

## Not included
Development time (HTTP API, progress migration, deployment), outbound data transfer, backups,
alerts and support plans, taxes and exchange rates. Cosmos DB also has a free tier on provisioned
throughput accounts (first 1,000 RU/s and 25 GB, per Microsoft Learn); it is not modelled here,
because the estimate uses serverless (whether the free tier applies to serverless is not verified).