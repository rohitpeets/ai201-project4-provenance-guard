"""
Transparency label generation.

Implements the three label variants from planning.md exactly, including the
split "uncertain" case (Case A: ambiguous middle, Case B: signals disagree).
"""


def generate_label(attribution: str, confidence: float, agreement_gap: float,
                    signal1_result: dict, signal2_result: dict) -> str:
    """
    Maps the combined attribution + scores to the exact label text from
    planning.md's "Transparency label design" section.

    Args:
        attribution: "likely_ai" | "likely_human" | "uncertain"
        confidence: the combined_score float
        agreement_gap: |signal1.score - signal2.score|
        signal1_result: {"score": float, "observations": list[str]}
        signal2_result: {"score": float, "metrics": dict, "observations": list[str]}

    Returns:
        The exact label string to show the user.
    """
    s1_obs = "; ".join(signal1_result["observations"][:2])
    s2_obs = "; ".join(signal2_result["observations"][:2])

    if attribution == "likely_ai":
        top_reasons = s1_obs if signal1_result["score"] >= signal2_result["score"] else s2_obs
        return (
            f"Combined score {confidence}. This content shows strong indicators "
            f"of AI generation. Top reasons: {top_reasons}."
        )

    if attribution == "likely_human":
        top_reasons = s1_obs if signal1_result["score"] <= signal2_result["score"] else s2_obs
        return (
            f"Combined score {confidence}. This content shows strong indicators "
            f"of human authorship. Top reasons: {top_reasons}."
        )

    # attribution == "uncertain" -- split into Case A vs Case B per planning.md
    if agreement_gap > 0.4:
        # Case B: signals actively disagree
        s1_lean = "AI-leaning" if signal1_result["score"] > 0.5 else "human-leaning"
        s2_lean = "AI-leaning" if signal2_result["score"] > 0.5 else "human-leaning"
        return (
            f"Our two detection signals disagreed on this content. "
            f"The LLM-based signal scored {signal1_result['score']} ({s1_obs}), "
            f"suggesting {s1_lean}. The stylometric signal scored "
            f"{signal2_result['score']} ({s2_obs}), suggesting {s2_lean}. "
            f"Because these signals measure different properties of the text "
            f"and reached different conclusions, we are not confident in "
            f"either direction. This is not a determination of AI or human "
            f"authorship. You may appeal this result for human review."
        )
    else:
        # Case A: signals agree but land in the ambiguous middle
        return (
            f"Our signals could not confidently determine the origin of this "
            f"content. The LLM-based signal scored {signal1_result['score']} "
            f"({s1_obs}), and the stylometric signal scored "
            f"{signal2_result['score']} ({s2_obs}). Both fall in the ambiguous "
            f"range — this is not a determination of AI or human authorship. "
            f"You may appeal this result for human review."
        )


if __name__ == "__main__":
    # Spec-conformance checks: confirm all three variants (plus both
    # uncertain sub-cases) produce text matching planning.md's wording.
    s1_ai = {"score": 0.9, "observations": ["Generic phrasing and formal tone", "Lacks personal voice"]}
    s2_ai = {"score": 0.85, "metrics": {}, "observations": ["Low vocabulary diversity", "Uniform sentence length"]}

    s1_human = {"score": 0.05, "observations": ["Conversational tone", "Personal anecdote present"]}
    s2_human = {"score": 0.1, "metrics": {}, "observations": ["High sentence length variance", "Irregular punctuation"]}

    s1_mid = {"score": 0.5, "observations": ["Some formal phrasing", "Some casual asides"]}
    s2_mid = {"score": 0.5, "metrics": {}, "observations": ["Moderate vocabulary diversity"]}

    s1_disagree_high = {"score": 0.9, "observations": ["Formal, generic phrasing"]}
    s2_disagree_low = {"score": 0.2, "metrics": {}, "observations": ["High structural variance"]}

    print("=== likely_ai ===")
    print(generate_label("likely_ai", 0.875, 0.05, s1_ai, s2_ai))

    print("\n=== likely_human ===")
    print(generate_label("likely_human", 0.075, 0.05, s1_human, s2_human))

    print("\n=== uncertain (Case A: agree, ambiguous middle) ===")
    print(generate_label("uncertain", 0.5, 0.0, s1_mid, s2_mid))

    print("\n=== uncertain (Case B: signals disagree) ===")
    print(generate_label("uncertain", 0.55, 0.7, s1_disagree_high, s2_disagree_low))