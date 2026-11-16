# AgriMind pitch deck guide

Use this guide to build a 7–10 minute deck for a pilot partner, funder, or early investor. The strongest story is operational: **extension teams need to decide which fields deserve attention, explain why, and get safe guidance to farmers with limited connectivity.** Keep satellite indices and agent architecture in support of that story.

## One-sentence pitch

**AgriMind helps agricultural extension teams prioritize field follow-up and prepare evidence-backed crop guidance, with agronomist review before a recommendation is approved.**

## Suggested 10-slide deck

### 1. Title and promise

**Headline:** AgriMind turns field data into reviewable farm decisions.

Include one sentence on the first customer: county or cooperative extension teams supporting maize farmers. Use a clear screenshot or one field map, not a technology collage.

### 2. The operational problem

Describe the specific workflow gap: officers have more fields to monitor than they can visit, observations arrive from different sources, and farmers may need advice when connectivity is weak.

Use evidence from interviews or a pilot: number of fields per officer, time spent on triage and travel, common decision delays, and how often farmers can be reached. If these numbers are not measured, present them as questions being tested rather than established facts.

### 3. Who feels the problem and who pays

Separate the roles:

- **User:** extension officer or agronomist reviewing fields and advisories.
- **Beneficiary:** farmer receiving clearer, timely guidance.
- **Potential buyer:** county agriculture department, cooperative, or agricultural program.

State which buyer you are pursuing first and why. Treat any county, cooperative, or government name as a target unless there is a documented partnership.

### 4. Product walkthrough

Show one real or clearly labeled demo field through the workflow:

1. Field and crop records are selected.
2. Saved satellite, weather, soil, and crop evidence is retrieved.
3. The system checks freshness and deterministic agronomic constraints.
4. AgriMind prepares a proposed action with evidence IDs.
5. An authorized officer reviews and approves or rejects it.
6. The intended farmer channel is shown, clearly marked as simulated or live.

Use actual screenshots and scrub personal information. Keep this slide focused on the officer’s task, not the code stack.

### 5. Why it is trustworthy

Explain the safeguards in plain language:

- Recommendations are tied to retrieved evidence and rule citations.
- Stale or missing observations can stop a recommendation.
- Planting and spraying have additional input and calendar checks.
- The system prepares drafts; an officer remains the decision-maker.

Show a sample advisory with its data dates, sources, missing inputs, and review status. Avoid saying “zero hallucinations”; describe the checks and show how they behave when data is insufficient.

### 6. Product and access

Show the current field dashboard and map, then explain how low-bandwidth access fits the workflow. Distinguish implemented interfaces from integrations that still need an end-to-end field test. The repository includes a Django dashboard, AgriMind advisory/review endpoints, chat, and a USSD callback; the Layer 2 README says outbound messaging is simulated.

### 7. Pilot plan and success measures

Propose a bounded pilot with a named partner only after agreement. Define:

- geography, crop, season, number of officers and fields
- baseline and comparison method
- data needed and who can authorize its use
- officer onboarding and support
- success thresholds and stop conditions

Measure review time per field, share of fields with fresh evidence, share of runs blocked for missing data, recommendation approval/rejection rate, farmer reach/response, field-visit allocation, and cost per field monitored. Do not claim impact before comparing with a baseline.

### 8. Business model hypotheses

Present these as options to validate, not current revenue:

- annual license for an extension office or cooperative
- pilot or implementation fee for onboarding and data integration
- per-field or per-season pricing for larger deployments
- sponsored access through agricultural programs or partners

Show a simple unit-economics worksheet once costs are known: support, satellite/data services, messaging, hosted inference, onboarding, and officer seats. The current OpenRouter free route is a prototype configuration with rate limits; do not promise free production inference.

### 9. Roadmap and defensibility

Prioritize near-term work that improves field use:

- reliable field data freshness and provenance
- offline or low-connectivity officer workflows
- tested SMS/USSD delivery and session recovery
- advisory outcome capture and feedback
- support for additional crops and local agronomic rules after maize validation

Describe defensibility as a hypothesis: local workflow integration, trusted review practices, longitudinal field records, and validated agronomic rules. Avoid implying proprietary data scale until it exists and can be used with permission.

### 10. The ask

Make one concrete request matched to the audience:

- **Pilot partner:** access to a small set of consenting fields, officer time, and agronomic review.
- **Funder:** support for a measured pilot, connectivity, and field evaluation.
- **Investor:** a defined amount for a defined milestone, with a budget and runway.

Close by stating the next decision and date. Do not end with a broad request to “support innovation.”

## Evidence to assemble before presenting

- 5–10 officer and farmer interviews with dates and consent notes
- a live demo using a field record that can be shared
- data provenance and freshness for each displayed metric
- the current status of each integration: demo, local, pilot-tested, or production
- baseline and pilot measurement plan
- realistic deployment costs, including messaging and hosted-model usage
- one signed pilot letter or partner confirmation, if available

## Claims in the existing README to verify first

The README includes precise claims such as 75% less field travel, zero hallucinated delivery, thousands of farmers, chemical savings, named county partners/personas, and specific regional statistics. Use these in a pitch only if you can provide a source, measurement method, date, and permission to identify the people or institutions. Otherwise label the scenario illustrative or omit the number.

Also distinguish the software’s current state from the deployment vision: the Layer 2 demo uses synthetic fixtures by default, live mode needs configured database/MCP/model access, and its README says outbound messaging is simulated. Do not present demo records or simulated USSD/SMS as pilot outcomes.

## Presentation style

- Use one claim per slide and a clear headline that states the takeaway.
- Show one real workflow end to end; keep architecture to an appendix.
- Prefer field screenshots, evidence cards, and one simple workflow diagram.
- Mark every metric as measured, sourced, target, or assumption.
- Put API names, model names, and implementation detail in backup slides.

## Useful appendix slides

1. System flow and data sources.
2. Evidence and validation rules.
3. Data privacy, consent, and human approval.
4. Pilot budget and unit economics.
5. Roadmap, risks, and dependencies.
