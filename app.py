"""
Provenance Guard - Flask app.

POST /submit  -> accepts {text, creator_id}, runs Signal 1 + Signal 2,
                 combines them, generates the real transparency label,
                 returns {content_id, attribution, confidence, label}, logs it.
POST /appeal  -> accepts {content_id, creator_id, reason}, verifies ownership,
                 updates status to appeal_pending, logs the appeal.
GET  /log     -> returns the most recent audit log entries as JSON.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

from signals import signal1_llm_score
from signal2 import signal2_stylometric_score
from scoring import combine_scores
from labels import generate_label

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
# In-memory stores. _submissions keeps full records (needed for appeal
# ownership verification); _audit_log is the append-only structured log.
_submissions = {}
_audit_log = []


def get_log(limit=20):
    """Return the most recent log entries, newest first."""
    return list(reversed(_audit_log[-limit:]))


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}

    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not isinstance(text, str):
        return jsonify({"error": "'text' (string) is required"}), 400
    if not creator_id or not isinstance(creator_id, str):
        return jsonify({"error": "'creator_id' (string) is required"}), 400

    signal1_result = signal1_llm_score(text)
    signal2_result = signal2_stylometric_score(text)

    scoring_result = combine_scores(signal1_result, signal2_result)
    confidence = scoring_result["combined_score"]
    agreement_gap = scoring_result["agreement_gap"]
    attribution = scoring_result["attribution"]

    label = generate_label(
        attribution, confidence, agreement_gap, signal1_result, signal2_result
    )

    content_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Full record, kept for appeal ownership verification.
    _submissions[content_id] = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "status": "classified",
    }

    log_entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "agreement_gap": agreement_gap,
        "llm_score": signal1_result["score"],
        "stylometric_score": signal2_result["score"],
        "status": "classified",
        "appealed": False,
    }
    _audit_log.append(log_entry)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    }), 200
@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}

    content_id = data.get("content_id")
    creator_id = data.get("creator_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not isinstance(content_id, str):
        return jsonify({"error": "'content_id' (string) is required"}), 400
    if not creator_id or not isinstance(creator_id, str):
        return jsonify({"error": "'creator_id' (string) is required"}), 400
    if not creator_reasoning or not isinstance(creator_reasoning, str):
        return jsonify({"error": "'creator_reasoning' (string) is required"}), 400

    submission = _submissions.get(content_id)
    if submission is None:
        return jsonify({"error": "no submission found for that content_id"}), 404

    if submission["creator_id"] != creator_id:
        rejected_entry = {
            "event": "appeal_rejected",
            "content_id": content_id,
            "attempted_creator_id": creator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "creator_id mismatch",
        }
        _audit_log.append(rejected_entry)
        return jsonify({"error": "creator_id does not match original submission"}), 403

    submission["status"] = "under_review"

    for entry in _audit_log:
        if entry.get("content_id") == content_id and entry.get("status") == "classified":
            entry["status"] = "under_review"
            entry["appealed"] = True

    appeal_id = str(uuid.uuid4())
    appeal_entry = {
        "event": "appeal_created",
        "appeal_id": appeal_id,
        "content_id": content_id,
        "creator_id": creator_id,
        "appeal_reasoning": creator_reasoning,
        "status": "under_review",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _audit_log.append(appeal_entry)

    return jsonify({
        "appeal_id": appeal_id,
        "status": "under_review",
        "content_id": content_id,
        "message": "Appeal received and is under review.",
    }), 200
@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()}), 200


if __name__ == "__main__":
    app.run(debug=True)