"""
Confidence scoring -- combines Signal 1 and Signal 2 into a single result.

Implements exactly the rules from planning.md's "Uncertainty representation"
section:
  combined_score = 0.5 * signal1.score + 0.5 * signal2.score
  thresholds: <0.4 likely_human, 0.4-0.6 uncertain, >0.6 likely_ai
  if |signal1.score - signal2.score| > 0.4 -> force "uncertain"
"""

SIGNAL1_WEIGHT = 0.5
SIGNAL2_WEIGHT = 0.5

LOW_THRESHOLD = 0.4    # below this -> likely_human
HIGH_THRESHOLD = 0.6   # above this -> likely_ai
DISAGREEMENT_THRESHOLD = 0.4  # gap above this forces "uncertain"


def combine_scores(signal1_result: dict, signal2_result: dict) -> dict:
    """
    Args:
        signal1_result: {"score": float, "observations": list[str]}
        signal2_result: {"score": float, "metrics": dict, "observations": list[str]}

    Returns:
        {
          "combined_score": float,
          "agreement_gap": float,
          "attribution": "likely_ai" | "likely_human" | "uncertain"
        }
    """
    s1 = signal1_result["score"]
    s2 = signal2_result["score"]

    combined_score = round(SIGNAL1_WEIGHT * s1 + SIGNAL2_WEIGHT * s2, 3)
    agreement_gap = round(abs(s1 - s2), 3)

    # Disagreement override takes priority over the threshold mapping.
    if agreement_gap > DISAGREEMENT_THRESHOLD:
        attribution = "uncertain"
    elif combined_score < LOW_THRESHOLD:
        attribution = "likely_human"
    elif combined_score > HIGH_THRESHOLD:
        attribution = "likely_ai"
    else:
        attribution = "uncertain"

    return {
        "combined_score": combined_score,
        "agreement_gap": agreement_gap,
        "attribution": attribution,
    }


if __name__ == "__main__":
    test_cases = [
        (0.1, 0.1, "likely_human", "both low, combined 0.1 < 0.4"),
        (0.9, 0.9, "likely_ai", "both high, combined 0.9 > 0.6"),
        (0.5, 0.5, "uncertain", "combined exactly mid-range"),
        (0.39, 0.39, "likely_human", "just under low threshold"),
        (0.41, 0.41, "uncertain", "just over low threshold, still in band"),
        (0.61, 0.61, "likely_ai", "just over high threshold"),
        (0.9, 0.2, "uncertain", "gap=0.7 > 0.4 -> forced uncertain despite combined=0.55"),
        (0.8, 0.35, "uncertain", "gap=0.45 > 0.4 -> forced uncertain"),
        (0.7, 0.4, "uncertain", "gap=0.3, combined=0.55 -> uncertain by threshold"),
    ]

    print("Spec-conformance check:")
    all_passed = True
    for s1, s2, expected, why in test_cases:
        result = combine_scores({"score": s1}, {"score": s2})
        passed = result["attribution"] == expected
        all_passed &= passed
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] s1={s1} s2={s2} -> {result} (expected {expected}: {why})")

    print("\nALL PASSED" if all_passed else "\nSOME FAILED -- check thresholds against planning.md")