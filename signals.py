"""
Detection signals for Provenance Guard.

Signal 1 (this milestone): LLM-based classification via Groq.
Per planning.md, this signal must return a JSON-shaped dict with:
  - score: float in [0, 1], 0 = confidently human, 1 = confidently AI
  - observations: list[str], specific textual cues noticed

Signal 2 (stylometric heuristics) is added in M4 -- not implemented here.
"""

import json
import os

from groq import Groq

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to your .env / api.env file."
            )
        _client = Groq(api_key=api_key)
    return _client


SIGNAL1_SYSTEM_PROMPT = """You are a text provenance classifier. Given a piece \
of text, judge whether it reads as human-written or AI-generated based on \
semantic and stylistic coherence (phrasing naturalness, transitions, argument \
structure, idiosyncrasy vs. genericness).

Respond with ONLY a JSON object, no other text, in exactly this shape:
{
  "score": <float between 0 and 1, where 0 = confidently human and 1 = confidently AI>,
  "observations": [<1 to 4 short strings, each a specific textual cue you noticed>]
}
"""


def signal1_llm_score(text: str) -> dict:
    """
    Signal 1: LLM-based classification.

    Args:
        text: the submitted text to evaluate.

    Returns:
        {
          "score": float in [0, 1],
          "observations": list[str]
        }

    Raises:
        ValueError if the model response can't be parsed into the expected shape.
    """
    client = _get_client()

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SIGNAL1_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Signal 1: could not parse model output as JSON: {raw!r}") from e

    score = parsed.get("score")
    observations = parsed.get("observations")

    if not isinstance(score, (int, float)) or not (0 <= score <= 1):
        raise ValueError(f"Signal 1: 'score' must be a float in [0,1], got {score!r}")
    if not isinstance(observations, list) or not all(isinstance(o, str) for o in observations):
        raise ValueError(f"Signal 1: 'observations' must be a list of strings, got {observations!r}")

    return {
        "score": float(score),
        "observations": observations,
    }


if __name__ == "__main__":
    # Quick manual check per the M3 verification plan: run this directly on
    # a few known examples BEFORE wiring into the /submit endpoint.
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
        "short": "Nice job on this.",
        "templated_legal": (
            "The undersigned hereby agrees to the terms set forth herein. "
            "This agreement shall remain in effect until terminated by either "
            "party with thirty (30) days written notice."
        ),
    }

    for name, sample_text in samples.items():
        result = signal1_llm_score(sample_text)
        print(f"\n[{name}]")
        print(f"  score: {result['score']}")
        print(f"  observations: {result['observations']}")