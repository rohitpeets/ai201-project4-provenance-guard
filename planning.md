# Provenance guard
AI-generated text is increasingly hard to distinguish from human writing, but a single confident "AI" or "human" verdict is risky — it's overconfident when wrong and leaves no way for a misjudged human writer to push back.
Provenance Guard treats detection as probabilistic rather than binary. It combines two independent signals (an LLM-based semantic judgment and a stylometric structural analysis) into a confidence score, attaches a transparency label that reflects uncertainty rather than asserting a verdict, and logs every decision for auditability. Because both signals can share blind spots (e.g. disciplined or non-native human writing resembling AI structurally), the system includes a built-in appeal flow so a flagged creator can contest the label against the original evidence.

## Detection Signals:

Signal 1: LLM Based classification

Prompts a LLM(via Groq) to judge whether a piece of text is human or AI generated.It gives back a score based on holistic and stylistic coherence.

Output: Not a bare score, It returns a JSON object with two fields:
- score ( is a float 0–1 (0 = confidently human, 1 = confidently AI ))
- observations(specific textual feature noticed in the text)

example:
{
  "score": 0.78,
  "observations": ["list of specific textual cues the model noticed"]
}

Signal 2: stylometric heuristics

Measures sentence length variance, type-token ratio (vocabulary diversity), punctuation density, average sentence complexity — computed directly, no model call.

Output:
- Score
- Metrics
- Observations

example:
{
  "score": 0.64,
  "metrics": {"sentence_length_variance": 2.1, "type_token_ratio": 0.31, "punctuation_density": 0.04, "avg_sentence_complexity": 1.8},
  "observations": ["metrics that crossed into AI-leaning territory, in plain language"]
}
## Uncertainiy representation

in case of a 0.6 score:
The 0.6 score is not a probability.The individual score from the two distinct signals sinify how much it varies from the base case (Training Data and guidelines for AI-Human generated text). The Laber must reflect this, avoid "60% chance this is Ai", Instead "leans AI, moderate confidence.

combining two signals:
combined_score=0.5*signalOne+0.5*signalTwo

Equal weights to both signals

For raw stylometric output:
clearly defined thresholds for each of the metrics
e.g. type-token ratio below 0.35 → AI-leaning, sentence length variance below 4 → AI-leaning

Normalize the scores into 0-1 .

Thresholds:
< 0.4   → likely human
0.4–0.6 → uncertain
> 0.6   → likely AI.
if the two signal scores differ by more than 0.4 (e.g. one says 0.9, the other says 0.2), force the label to "uncertain" regardless of the average

## Transparency label design
- Likely AI (Signals agree)
"Combined Score {Score}.The content shows string indicators of AI generation.Top Reasons:{1-2 observations from signal1 and signal2}

- Likely Human (Signals agree)
"Combined score {Score}.This content shows strong indicators of human authorship.Top Observations{1-2 observations from signal1 and signal2.}

- Uncertain 
"Our signals could not confidently determine the origin of this content. The LLM-based signal scored {signal1.score} ({1-2 signal1 observations}), and the stylometric signal scored {signal2.score} ({1-2 signal2 observations}). Both fall in the ambiguous range — this is not a determination of AI or human authorship. You may appeal this result for human review."

## Appeal Workflow
Any response other than "Likely Human" is appealabel.

The orignal submitter if every submission is identified via a submitter_id. The person related to a specific submissions can appeal it.

What they provide:
- The original submission being contested(submission_Id).
- The submitter_id.
- A text explaination with context

When an appeal is received:
- The original submission's status changes to appeal_pending.The other properties like the Combined score, Signal Scores and observations are stored for record.
- An appeal record gets created(separate from the submission record),containing the appeal reason, appeal_id and status "pending".

## Edge cases
1. ESL or children's writing — limited vocabulary (low type-token ratio) and simple, uniform sentence structure from developing language skill look statistically identical to AI-generated simplicity. Signal 2 will likely flag it as AI-leaning.
2. Templated professional/legal writing (cover letters, contracts, incident reports) — deliberate uniformity, formal tone, and boilerplate phrasing match what both signals associate with AI output. Both signals tend to agree here, producing a high-confidence false positive with no agreement_gap to catch it.
Both cases share the same root issue: authentic human constraint (skill level, professional convention) can produce the same statistical signature as AI generation, which neither signal can currently distinguish

## Architecture
SUBMISSION FLOW

  POST /submit
  (raw text, submitter_id)
       |
       v
  +-------------------+
  | Signal 1: LLM      |
  | (Groq) -> score,   |
  | observations       |
  +-------------------+
       |
       v
  +-------------------+
  | Signal 2:          |
  | Stylometrics ->    |
  | score, metrics,    |
  | observations       |
  +-------------------+
       |
       v
  +-------------------+
  | Confidence scoring |
  | combined_score,    |
  | agreement_gap      |
  +---------+---------+
            |
   +--------+--------+
   |                 |
   v                 v
+-----------+   +-------------+
| Transparency|  | Audit log   |
| label       |  | (full       |
| (text)      |  | record, w/  |
|             |  | submitter_id)|
+-----------+   +-------------+
       \               /
        \             /
         v           v
         Response (submission_id, scores, label)


APPEAL FLOW

  POST /appeal
  (submission_id, submitter_id, reason)
       |
       v
  +-------------------+
  | Verify submitter_id |
  | matches the         |
  | original submission |
  +---------+---------+
       |  match              |  mismatch
       v                      v
  +-------------------+   403 Forbidden
  | Status update      |   (logged as
  | (submission ->     |    rejected attempt)
  | appeal_pending)     |
  +-------------------+
       |
       v
  +-------------------+
  | Audit log          |
  | (appeal record      |
  | linked by           |
  | submission_id +     |
  | submitter_id)        |
  +-------------------+
       |
       v
  Response (appeal_id, status: pending)

## AI Tool Plan

**M3 — Submission endpoint + first signal**
Provide: Detection signals (Signal 1) + submission diagram. Ask for: Flask `/submit` skeleton + `signal1_llm_score(text)`. Verify: test the function directly on a few known examples (clearly AI, clearly human, templated) before wiring into the endpoint.

**M4 — Second signal + confidence scoring**
Provide: Detection signals (Signal 2) + confidence scoring + diagram. Ask for: `signal2_stylometric_score(text)` + `combine_scores()`. Verify: confirm both signals move differently on the same test set, and a forced-disagreement case correctly lands on "uncertain."

**M5 — Production layer**
Provide: Transparency labels + appeals workflow + appeal diagram. Ask for: `generate_label()` + the `/appeal` endpoint. Verify: hit all three labels with test inputs, confirm matching `submitter_id` moves status to `appeal_pending` and mismatched ones get rejected and logged.

