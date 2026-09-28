"""Sublab Hard: extract constrained CVs, then rank model scores in Python."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from grant_common import DATA, ROOT, call_model, compact_json, parse_json_object, read_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CV_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_id": {"type": "string"}, "full_name": {"type": ["string", "null"]},
        "degree": {"type": ["string", "null"]}, "graduation_year": {"type": ["integer", "null"]},
        "gpa_4_scale": {"type": ["number", "null"]}, "gpa_original": {"type": ["string", "null"]},
        "languages": {"type": "array", "items": {"type": "string"}},
        "published_peer_reviewed_outputs": {"type": ["integer", "null"], "minimum": 0},
        "nonpublished_outputs": {"type": "array", "items": {"type": "string"}},
        "relevant_experience_months": {"type": ["integer", "null"], "minimum": 0},
        "uncounted_experience": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["candidate_id", "full_name", "degree", "graduation_year", "gpa_4_scale",
                 "gpa_original", "languages", "published_peer_reviewed_outputs", "nonpublished_outputs",
                 "relevant_experience_months", "uncounted_experience", "evidence", "ambiguities"],
    "additionalProperties": False,
}
SCORE_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "number", "minimum": 0, "maximum": 5}
                   for key in ("academic", "research", "experience")},
    "required": ["academic", "research", "experience"], "additionalProperties": False,
}


def extraction_prompt(candidate_id: str, story: str) -> str:
    """State every extraction rule in the prompt so it is inspectable and repeatable."""
    shape = {
        "candidate_id": candidate_id, "full_name": None, "degree": None, "graduation_year": None,
        "gpa_4_scale": None, "gpa_original": None, "languages": [],
        "published_peer_reviewed_outputs": None, "nonpublished_outputs": [],
        "relevant_experience_months": None, "uncounted_experience": [], "evidence": {}, "ambiguities": [],
    }
    return "\n\n".join([
        "Extract one scholarship CV from the story below. Return exactly one JSON object, no prose.",
        "Rules: Every fact not explicitly stated is null; never estimate. Record a GPA on its original "
        "scale in gpa_original and convert it mathematically to gpa_4_scale (value / scale_max * 4); "
        "do not invent a GPA. Count a publication only if the story says published or accepted AND says "
        "peer-reviewed. Put submitted, under review, in preparation, planned, and in press outputs in "
        "nonpublished_outputs and do not count them. Count only relevant-experience months with stated "
        "dates/duration; overlapping intervals count once. If a field contradicts itself, set that field "
        "to null and put both claims in ambiguities: never resolve or average. evidence maps every filled "
        "field to one or more short verbatim quotes from the story.",
        "Required shape:\n" + compact_json(shape),
        "Story:\n" + story,
    ])


def validate(schema: dict[str, Any], value: dict[str, Any]) -> list[str]:
    return [error.message for error in Draft202012Validator(schema).iter_errors(value)]


def normalise_cv(value: dict[str, Any]) -> dict[str, Any]:
    """Normalise harmless JSON representation differences before validating.

    A single evidence quote and a one-item evidence list mean the same thing;
    the stored record always uses the documented list form.  The model sometimes
    emits a bare original GPA despite quoting its scale, so retain the scale in
    the field required by the assignment rather than discarding that evidence.
    """
    value = dict(value)
    evidence = dict(value.get("evidence") or {})
    for key, quote in list(evidence.items()):
        if isinstance(quote, str):
            evidence[key] = [quote]
    value["evidence"] = evidence
    original = value.get("gpa_original")
    if isinstance(original, dict) and "value" in original and "scale_max" in original:
        value["gpa_original"] = f"{original['value']} / {original['scale_max']}"
        original = value["gpa_original"]
    if isinstance(original, (int, float)) or (isinstance(original, str) and "/" not in original):
        quote = " ".join(evidence.get("gpa_original", []))
        scale = re.search(r"(?:out of|on a)\s*(\d+(?:\.\d+)?)|"
                          r"(\d+(?:\.\d+)?)\s*(?:scale|шкаласы)", quote, re.I)
        scale_value = next((group for group in scale.groups() if group), None) if scale else None
        value["gpa_original"] = f"{original} / {scale_value}" if scale_value else str(original)
    return value


def extract_one(candidate_id: str, story: str) -> dict[str, Any]:
    reply = call_model([{"role": "system", "content": "You are a careful information extractor."},
                        {"role": "user", "content": extraction_prompt(candidate_id, story)}], max_tokens=1300)
    row: dict[str, Any] = {"candidate_id": candidate_id, "story": story, **reply, "parsed": False,
                           "valid": False}
    try:
        cv = normalise_cv(parse_json_object(reply["text"]))
        row.update({"parsed": True, "cv": cv, "validation_errors": validate(CV_SCHEMA, cv)})
        row["valid"] = not row["validation_errors"]
    except ValueError as exc:
        row["error"] = str(exc)
    return row


def score_prompt(cv: dict[str, Any], rubric: dict[str, Any]) -> str:
    return "\n\n".join([
        "Score this extracted candidate record only. Do not repair missing or contradicted fields. "
        "Use the supplied rubric and return exactly JSON with numeric academic, research, experience values "
        "from 0 through 5. Do not calculate a weighted total or choose a winner.",
        "Rubric:\n" + compact_json(rubric), "Candidate record:\n" + compact_json(cv),
        'Exact response shape: {"academic": 0, "research": 0, "experience": 0}',
    ])


def score_one(extraction: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    candidate_id = extraction["candidate_id"]
    if not extraction.get("valid"):
        return {"candidate_id": candidate_id, "parsed": False, "valid": False,
                "error": "extraction invalid; no score call made"}
    reply = call_model([{"role": "system", "content": "You score consistently against a stated rubric."},
                        {"role": "user", "content": score_prompt(extraction["cv"], rubric)}], max_tokens=250)
    row: dict[str, Any] = {"candidate_id": candidate_id, **reply, "parsed": False, "valid": False}
    try:
        score = parse_json_object(reply["text"])
        row.update({"parsed": True, "score": score, "validation_errors": validate(SCORE_SCHEMA, score)})
        row["valid"] = not row["validation_errors"]
        if row["valid"]:
            weights = {criterion["id"]: criterion["weight"] for criterion in rubric["criteria"]}
            row["weighted_total"] = round(sum(float(score[key]) * weights[key] for key in weights), 2)
    except ValueError as exc:
        row["error"] = str(exc)
    return row


def prose_winner(extractions: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    records = [{"candidate_id": row["candidate_id"], "cv": row.get("cv")} for row in extractions]
    return call_model([
        {"role": "system", "content": "You are a scholarship committee member. Give a concise prose recommendation."},
        {"role": "user", "content": "Which candidate should win and why? Use this rubric and extracted records. "
         "This is a separate prose judgement; do not pretend it is the programmatic ranking.\nRubric:\n" +
         compact_json(rubric) + "\nRecords:\n" + compact_json(records)},
    ], max_tokens=500)


def null_fields(cv: dict[str, Any]) -> list[str]:
    return [key for key, value in cv.items() if value is None]


def detected_traps(row: dict[str, Any]) -> list[str]:
    cv = row.get("cv", {})
    text = row["story"].lower()
    traps = []
    if cv.get("gpa_4_scale") is None and not any("GPA" in item for item in cv.get("ambiguities", [])):
        traps.append("no GPA stated")
    if re.search(r"out of 5|5\.0", text):
        traps.append("non-4.0 GPA")
    if cv.get("nonpublished_outputs"):
        traps.append("unpublished paper")
    if cv.get("ambiguities"): traps.append("contradiction")
    return traps


def print_report(extractions: list[dict[str, Any]], scores: list[dict[str, Any]], prose: dict[str, Any]) -> None:
    print("=== Sublab Hard: CV extraction ===")
    for row in extractions:
        cv = row.get("cv", {})
        print(f"{row['candidate_id']}: parsed={row['parsed']} valid={row['valid']} "
              f"null={','.join(null_fields(cv)) or 'none'} traps={'; '.join(detected_traps(row)) or 'none'}")
    print("\n=== Scores; total is computed by code ===")
    for row in scores:
        print(f"{row['candidate_id']}: {row.get('score', {})}; total={row.get('weighted_total', 'ERROR')}")
    valid = [row for row in scores if row.get("valid")]
    if valid:
        winner = max(valid, key=lambda row: row["weighted_total"])
        print(f"winner (code): {winner['candidate_id']} at {winner['weighted_total']:.2f}")
    print("\nmodel prose recommendation:\n" + prose["text"])


def main() -> None:
    rubric = read_json(DATA / "candidate_rubric.json")
    paths = sorted((DATA / "candidates").glob("story-*.md"))
    extractions = [extract_one(path.stem, path.read_text(encoding="utf-8")) for path in paths]
    scores = [score_one(row, rubric) for row in extractions]
    prose = prose_winner(extractions, rubric)
    output = {"extractions": extractions, "scores": scores, "prose": prose}
    out = ROOT / "outputs"; out.mkdir(exist_ok=True)
    (out / "hard_run.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(extractions, scores, prose)
    print("\nwrote outputs/hard_run.json")


if __name__ == "__main__":
    main()
