# ai201-project4-provenance-guard

A backend system that classifies submitted text as likely AI-generated, likely human-written, or uncertain, using two independent signals, a confidence score, transparency labels, an appeals workflow, rate limiting, and an audit log.

## Architecture overview

A submission travels through six stages before a creator sees a result.

`POST /submit` receives the raw text and `creator_id`. The text is passed independently to both detection signals: Signal 1 (LLM-based, via Groq) returns a semantic score and observations; Signal 2 (stylometric heuristics, pure Python) returns a structural score, raw metrics, and observations. Neither signal sees the other's output.

Both scores feed into confidence scoring, which produces a `combined_score`, an `agreement_gap` (how far apart the two signals landed), and an `attribution` (`likely_ai` / `likely_human` / `uncertain`) — using the weighting and thresholds from planning.md, including the override that forces "uncertain" when the signals disagree by more than 0.4.

The attribution and scores then generate the transparency label — the exact text a creator sees, picked from the three (really four, counting the split uncertain case) variants written out below.

In parallel, a structured entry is written to the audit log — timestamp, content ID, attribution, combined confidence, both individual signal scores, and an `appealed` flag — before the response (`content_id`, `attribution`, `confidence`, `label`) is returned to the caller.

If a creator later disputes the result, `POST /appeal` looks up the original submission by `content_id`, verifies the appealing `creator_id` matches the original submitter, and — on a match — updates the submission's status to `under_review` in place (the original scores are preserved, not overwritten) and writes a new linked audit log entry. A mismatched `creator_id` is rejected with 403 and the rejected attempt is itself logged.

```
SUBMISSION FLOW

  POST /submit (text, creator_id)
       |
       v
  Signal 1: LLM (Groq) -> score, observations
       |
       v
  Signal 2: Stylometrics -> score, metrics, observations
       |
       v
  Confidence scoring -> combined_score, agreement_gap, attribution
       |
   +---+---+
   |       |
   v       v
Transparency   Audit log
label (text)   (full record)
   |       |
   +---+---+
       v
Response (content_id, attribution, confidence, label)


APPEAL FLOW

  POST /appeal (content_id, creator_id, creator_reasoning)
       |
       v
  Verify creator_id matches original submission
       |
   +---+---+
   |       |
 match   mismatch
   |       |
   v       v
Status -> under_review     403 Forbidden (logged)
   |
   v
Audit log (appeal record, linked by content_id)
   |
   v
Response (appeal_id, status: under_review)
```
## Detection signals

**Signal 1: LLM-based classification**
Prompts an LLM (via Groq) to judge whether a piece of text is human or AI generated. Gives back a score based on holistic and stylistic coherence. Returns `{score, observations}`.

**Signal 2: Stylometric heuristics**
Measures sentence length variance, type-token ratio, punctuation density, average sentence complexity — computed directly, no model call. Returns `{score, metrics, observations}`.

These two are genuinely independent: one is semantic, one is structural. That's why combining them is more informative than either alone.

**What I'd change for real deployment:** calibrate the two undocumented stylometric thresholds against real labeled data instead of placeholders, and restructure Signal 1 to output a verdict + confidence separately instead of a single 0–1 score — testing showed cases where the score contradicted the model's own observations.

## Confidence scoring

`combined_score = 0.5*signalOne + 0.5*signalTwo`. Equal weights.

Thresholds: `<0.4` likely human, `0.4–0.6` uncertain, `>0.6` likely AI. If the two signals differ by more than 0.4, force "uncertain" regardless of the average.

A 0.6 score is not a probability — it signifies how much the text varies from the base case, not a percentage chance.

**Example 1 — high confidence:**
```json
{"content_id": "9396234c-798b-4e8b-889b-a28eabb8e248", "attribution": "likely_ai", "confidence": 0.8, "llm_score": 0.85, "stylometric_score": 0.75, "agreement_gap": 0.1}
```

**Example 2 — low confidence, disagreement:**
```json
{"content_id": "c3210f4f-7d63-442a-83a5-c9a048dabea3", "attribution": "uncertain", "confidence": 0.375, "llm_score": 0.0, "stylometric_score": 0.75, "agreement_gap": 0.75}
```
Raw average here is 0.375, which alone would round to "likely human" — but the 0.75 disagreement gap forced "uncertain" instead, since two signals that disagree this much shouldn't be blended into a confident answer.

## Transparency labels

**Likely AI:** "Combined score {score}. The content shows strong indicators of AI generation. Top reasons: {1-2 observations}."

**Likely human:** "Combined score {score}. This content shows strong indicators of human authorship. Top observations: {1-2 observations}."

**Uncertain (signals agree, ambiguous middle):** "Our signals could not confidently determine the origin of this content. The LLM-based signal scored {signal1.score} ({observations}), and the stylometric signal scored {signal2.score} ({observations}). Both fall in the ambiguous range — this is not a determination of AI or human authorship. You may appeal this result for human review."

**Uncertain (signals disagree):** "Our two detection signals disagreed on this content. The LLM-based signal scored {signal1.score} ({observations}), suggesting {AI/human}-leaning. The stylometric signal scored {signal2.score} ({observations}), suggesting {AI/human}-leaning. Because these signals measure different properties of the text and reached different conclusions, we are not confident in either direction. This is not a determination of AI or human authorship. You may appeal this result for human review."

## Appeals workflow

Any response other than "likely human" is appealable. The original submitter is identified via `creator_id`; only they can appeal.

What they provide: `content_id`, `creator_id`, `creator_reasoning`.

When received: status changes to `under_review` (original scores preserved, not overwritten). An appeal record is created, linked by `content_id`, logged separately with its own `appeal_id`. Mismatched `creator_id` gets rejected with 403 and logged.

**Live example:**
```json
{"event": "appeal_created", "appeal_id": "729d1ff5-31d1-42ad-bb87-1c1144dc394f", "content_id": "9396234c-798b-4e8b-889b-a28eabb8e248", "creator_id": "field-fix-test", "appeal_reasoning": "confirming appeal_reasoning and under_review fields", "status": "under_review"}
```
Original entry, updated in place:
```json
{"content_id": "9396234c-798b-4e8b-889b-a28eabb8e248", "attribution": "likely_ai", "confidence": 0.8, "status": "under_review", "appealed": true}
```

## Rate limiting

`10 per minute; 100 per day` on `/submit`.

A writer testing/revising drafts might submit several pieces in a sitting — 10/minute covers that without feeling restrictive, well below what a flood script would attempt. 100/day caps total exposure (and API cost) over a full day without blocking real use.

**Test (12 rapid requests):**
```
200 200 200 200 200 200 200 200 200 200 429 429
```

## Audit log

Every submission writes a structured JSON entry — timestamp, content ID, attribution, confidence, both signal scores, agreement gap, and an `appealed` flag. `GET /log` exposes recent entries.

Sample (submission + appeal + rejected appeal, same content):
```json
{
  "entries": [
    {"event": "appeal_rejected", "attempted_creator_id": "someone-else", "content_id": "4b490ef0-ad74-4b63-97df-a6cab273a986", "reason": "creator_id mismatch"},
    {"event": "appeal_created", "appeal_id": "07de1ce9-318b-48a0-b764-8464b5b9d7f7", "content_id": "4b490ef0-ad74-4b63-97df-a6cab273a986", "creator_id": "test-user-1", "appeal_reasoning": "I wrote this myself, it is not AI-generated.", "status": "under_review"},
    {"content_id": "4b490ef0-ad74-4b63-97df-a6cab273a986", "creator_id": "test-user-1", "attribution": "likely_human", "confidence": 0.142, "llm_score": 0.0, "stylometric_score": 0.284, "status": "under_review", "appealed": true}
  ]
}
```

## Known limitations

**1. Signal 1's score can contradict its own observations.** The same casual text scored 0.0 in one run and 0.7 in another, with observations describing human-typical traits both times. A consistency instruction in the prompt helped but didn't fully fix it. Real fix (separate verdict + confidence fields) was identified but deferred.

**2. Stylometric heuristics misfire on formal/academic register.** A deliberately AI-sounding formal paragraph scored human-leaning on stylometrics, because it had high vocabulary diversity and high sentence variance — the opposite of what the "AI = uniform" assumption expects. Distinct from the ESL/legal-writing edge cases already in planning.md — this is a register-mismatch problem, not a vocabulary-limitation one.

Both edge cases from planning.md still apply too: ESL/children's writing (low type-token ratio from developing skill, not AI), and templated legal/professional writing (deliberate uniformity both signals associate with AI).

## Spec reflection

**Helped:** the explicit thresholds in planning.md (`<0.4`/`0.4–0.6`/`>0.6`, disagreement override at 0.4) gave scoring something concrete to implement and test against — I wrote 9 boundary-case tests directly against those numbers, all passed.

**Diverged:** planning.md only gave explicit thresholds for 2 of Signal 2's 4 metrics. I had to invent placeholders for `punctuation_density` and `avg_sentence_complexity`, flagged in code as uncalibrated guesses. This likely contributed to Known Limitation #2.

## AI usage

**1. Confidence scoring (`scoring.py`).** Asked the AI tool to implement `combine_scores()` per planning.md's weights and thresholds. Rather than trust it on sight, had it generate 9 boundary-case tests (e.g. exactly 0.39 vs 0.41) — all passed, confirming the real numbers matched, not just plausible-looking ones.

**2. Signal 1 prompt debugging.** When score/observation contradictions showed up live, the AI's first fix was a consistency instruction in the prompt. It worked on the original failing case, but the same contradiction reappeared in reverse on a different input. Rather than keep patching, I chose to document the limitation honestly instead of building the larger structural fix, given project scope.
