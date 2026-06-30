"""
Signal 2: stylometric heuristics.

Per planning.md, this signal must return:
  - score: float in [0, 1], 0 = human-leaning, 1 = AI-leaning
  - metrics: dict of the raw computed values
  - observations: list[str], plain-language notes on which metrics
                  crossed into AI-leaning territory

Computed directly in Python -- no model call.
"""

import re
import statistics


def _split_sentences(text: str) -> list[str]:
    # Simple sentence splitter on ./!/? -- good enough for heuristic purposes.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s]


def _sentence_length_variance(sentences: list[str]) -> float:
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    return statistics.pvariance(lengths)


def _type_token_ratio(text: str) -> float:
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def _punctuation_density(text: str) -> float:
    if not text:
        return 0.0
    punct_count = len(re.findall(r"[.,;:!?\-—()]", text))
    return punct_count / len(text)


def _avg_sentence_complexity(sentences: list[str]) -> float:
    # Proxy for complexity: average comma count per sentence (clause indicator).
    if not sentences:
        return 0.0
    comma_counts = [s.count(",") for s in sentences]
    return sum(comma_counts) / len(sentences)


# --- Normalization thresholds, per planning.md's "Uncertainty representation"
# section. Two thresholds are spelled out explicitly there:
#   - type_token_ratio < 0.35 -> AI-leaning
#   - sentence_length_variance < 4 -> AI-leaning
# The other two metrics (punctuation_density, avg_sentence_complexity) are NOT
# given explicit thresholds in planning.md. Reasonable defaults are used below
# and flagged here -- these should be recalibrated against real labeled
# samples, not treated as spec-confirmed numbers.
TTR_AI_THRESHOLD = 0.35
SENTENCE_VAR_AI_THRESHOLD = 4.0
PUNCT_DENSITY_AI_THRESHOLD = 0.03   # NOT in planning.md -- placeholder, recalibrate
COMPLEXITY_AI_THRESHOLD = 0.5       # NOT in planning.md -- placeholder, recalibrate


def _normalize_metric(value: float, threshold: float, lower_is_ai: bool) -> float:
    """
    Maps a raw metric into [0, 1] AI-leaning score using a simple linear
    ramp around the threshold. This is a heuristic normalization, not a
    statistically calibrated one -- per planning.md, real calibration
    against labeled samples is a known TODO, not done here.
    """
    if threshold == 0:
        return 0.5
    ratio = value / threshold
    if lower_is_ai:
        # value below threshold -> AI-leaning (score closer to 1)
        score = 1.0 - min(ratio, 1.0)
    else:
        # value above threshold -> AI-leaning
        score = min(ratio, 1.0)
    return max(0.0, min(1.0, score))


def signal2_stylometric_score(text: str) -> dict:
    """
    Signal 2: stylometric heuristics.

    Returns:
        {
          "score": float in [0, 1],
          "metrics": {raw computed values},
          "observations": list[str]
        }
    """
    sentences = _split_sentences(text)

    sentence_length_variance = _sentence_length_variance(sentences)
    type_token_ratio = _type_token_ratio(text)
    punctuation_density = _punctuation_density(text)
    avg_sentence_complexity = _avg_sentence_complexity(sentences)

    metrics = {
        "sentence_length_variance": round(sentence_length_variance, 3),
        "type_token_ratio": round(type_token_ratio, 3),
        "punctuation_density": round(punctuation_density, 3),
        "avg_sentence_complexity": round(avg_sentence_complexity, 3),
    }

    sub_scores = {
        "sentence_length_variance": _normalize_metric(
            sentence_length_variance, SENTENCE_VAR_AI_THRESHOLD, lower_is_ai=True
        ),
        "type_token_ratio": _normalize_metric(
            type_token_ratio, TTR_AI_THRESHOLD, lower_is_ai=True
        ),
        "punctuation_density": _normalize_metric(
            punctuation_density, PUNCT_DENSITY_AI_THRESHOLD, lower_is_ai=True
        ),
        "avg_sentence_complexity": _normalize_metric(
            avg_sentence_complexity, COMPLEXITY_AI_THRESHOLD, lower_is_ai=True
        ),
    }

    # Equal-weighted average of the four sub-scores -> Signal 2's final score.
    score = sum(sub_scores.values()) / len(sub_scores)

    observations = []
    if type_token_ratio < TTR_AI_THRESHOLD:
        observations.append(
            f"Vocabulary diversity is low (type-token ratio {type_token_ratio:.2f}, "
            f"below the {TTR_AI_THRESHOLD} AI-leaning threshold)."
        )
    if sentence_length_variance < SENTENCE_VAR_AI_THRESHOLD:
        observations.append(
            f"Sentence length variance is low ({sentence_length_variance:.2f}, "
            f"below the {SENTENCE_VAR_AI_THRESHOLD} AI-leaning threshold)."
        )
    if punctuation_density < PUNCT_DENSITY_AI_THRESHOLD:
        observations.append(
            f"Punctuation density is low ({punctuation_density:.3f})."
        )
    if avg_sentence_complexity < COMPLEXITY_AI_THRESHOLD:
        observations.append(
            f"Average sentence complexity is low ({avg_sentence_complexity:.2f})."
        )
    if not observations:
        observations.append("No metrics crossed into AI-leaning territory.")

    return {
        "score": round(score, 3),
        "metrics": metrics,
        "observations": observations,
    }


if __name__ == "__main__":
    samples = {
        "clearly_ai": (
            "In conclusion, it is important to note that artificial intelligence "
            "has fundamentally transformed numerous industries, and furthermore, "
            "its continued development promises to deliver significant benefits "
            "across a wide range of sectors moving forward."
        ),
        "clearly_human": (
            "ok so I tried fixing the bug for like 3 hours last night and turns "
            "out it was a typo the whole time lol. anyway here's the PR, lmk if "
            "the tests look weird to you"
        ),
        "templated_legal": (
            "The undersigned hereby agrees to the terms set forth herein. "
            "This agreement shall remain in effect until terminated by either "
            "party with thirty (30) days written notice."
        ),
    }

    for name, sample_text in samples.items():
        result = signal2_stylometric_score(sample_text)
        print(f"\n[{name}]")
        print(f"  score: {result['score']}")
        print(f"  metrics: {result['metrics']}")
        print(f"  observations: {result['observations']}")