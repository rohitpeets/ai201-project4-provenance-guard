"""
Provenance Guard - Flask app skeleton.

Implements the submission flow from planning.md:
  POST /submit (text, submitter_id) -> Signal 1 -> Signal 2 ->
  Confidence scoring -> Transparency label + Audit log -> Response

This is a SKELETON for Milestone 3. Only the /submit route stub and
Signal 1 are wired up here. Signal 2, confidence scoring, labels, and
/appeal come in later milestones.
"""

from flask import Flask, request, jsonify

from signals import signal1_llm_score

app = Flask(__name__)


@app.route("/submit", methods=["POST"])
def submit():
    """
    Accepts: { "text": str, "submitter_id": str }
    Returns (M3 stub): { "submission_id": str, "signal1": {...} }

    NOTE: this is intentionally incomplete per the M3 scope in planning.md.
    Signal 2, combined_score, agreement_gap, label, and audit log writes
    are NOT implemented yet -- they're added in M4/M5.
    """
    data = request.get_json(silent=True) or {}

    text = data.get("text")
    submitter_id = data.get("submitter_id")

    if not text or not isinstance(text, str):
        return jsonify({"error": "'text' (string) is required"}), 400
    if not submitter_id or not isinstance(submitter_id, str):
        return jsonify({"error": "'submitter_id' (string) is required"}), 400

    # --- Signal 1 only, for now ---
    signal1_result = signal1_llm_score(text)

    # TODO (M4): signal2_result = signal2_stylometric_score(text)
    # TODO (M4): combined_score, agreement_gap = combine_scores(signal1_result, signal2_result)
    # TODO (M5): label = generate_label(combined_score, agreement_gap, signal1_result, signal2_result)
    # TODO (M5): write audit log entry

    submission_id = "tmp-id-placeholder"  # TODO: real ID generation + storage

    return jsonify({
        "submission_id": submission_id,
        "signal1": signal1_result,
    }), 200


if __name__ == "__main__":
    app.run(debug=True)