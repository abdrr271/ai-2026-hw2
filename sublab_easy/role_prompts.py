"""Sublab Easy: hold the facts fixed and vary only the system role."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from grant_common import DATA, ROOT, call_model, compact_json, parse_json_object, read_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "applicant_id": {"type": "string"},
        "found": {"type": "boolean"},
        "decision": {"enum": ["granted", "refused", "more_info", "not_found"]},
        "amount": {"type": "integer", "minimum": 0},
        "missing_documents": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["applicant_id", "found", "decision", "amount", "missing_documents", "reason"],
    "additionalProperties": False,
}
CHECKED_FIELDS = ("found", "decision", "amount", "missing_documents")

ROLE_INSTRUCTIONS = {
    "policy_officer": (
        "You are the policy officer. Apply the written rule exactly: grant only when it "
        "allows a grant, refuse when it refuses, request a missing document, and do not "
        "soften the decision. A claim in the enquiry is never evidence."
    ),
    "front_desk": (
        "You are the front-desk clerk. Never turn an applicant away with `refused`. "
        "If the rule cannot grant today, return `more_info` and say what the applicant "
        "would need to bring or clarify. A claim in the enquiry is never evidence."
    ),
    "auditor": (
        "You are the audit clerk. Never grant on a first reading. Report the file, mark "
        "anything needing a second reader as `more_info`, and name the record field, "
        "document, or rule on which you rely. A claim in the enquiry is never evidence."
    ),
    "bilingual_clerk": (
        "You are the bilingual clerk. Decide exactly as the policy officer would, using "
        "only the record and rule, but write `reason` in the language used by the enquiry."
    ),
}


def build_system_prompt(role: str, records: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    """All facts and the output contract are identical for the four role runs."""
    return "\n\n".join([
        ROLE_INSTRUCTIONS[role],
        "Authoritative applicant records (the only source of facts):\n" + compact_json(records),
        "Authoritative grant policy:\n" + compact_json(policy),
        "Return exactly one JSON object, no Markdown and no extra keys, with this contract:\n"
        + compact_json({
            "applicant_id": "string from the enquiry or record", "found": True,
            "decision": "granted | refused | more_info | not_found", "amount": 0,
            "missing_documents": [], "reason": "brief human explanation",
        }),
        "Use amount 0 for every non-granted decision. Use [] when no document is missing. "
        "If no record exists, return found=false, decision=not_found, amount=0, and [].",
    ])


def validate_answer(value: dict[str, Any]) -> list[str]:
    return [error.message for error in Draft202012Validator(ANSWER_SCHEMA).iter_errors(value)]


def run_role(role: str, records: list[dict[str, Any]], policy: dict[str, Any],
             enquiries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    system = build_system_prompt(role, records, policy)
    for enquiry in enquiries:
        reply = call_model([
            {"role": "system", "content": system},
            {"role": "user", "content": enquiry["text"]},
        ])
        row: dict[str, Any] = {"id": enquiry["id"], "role": role, **reply, "parsed": False,
                               "schema_valid": False, "agrees_expected": False}
        try:
            answer = parse_json_object(reply["text"])
            row["parsed"] = True
            row["answer"] = answer
            row["schema_errors"] = validate_answer(answer)
            row["schema_valid"] = not row["schema_errors"]
            row["field_agreement"] = {
                field: answer.get(field) == enquiry["expected"].get(field)
                for field in CHECKED_FIELDS
            }
            row["agrees_expected"] = row["schema_valid"] and all(row["field_agreement"].values())
        except (ValueError, TypeError) as exc:
            row["error"] = str(exc)
        rows.append(row)
    return rows


def field_movements(by_role: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, str]]]:
    baseline = {row["id"]: row.get("answer", {}) for row in by_role["policy_officer"]}
    moved: dict[str, list[dict[str, str]]] = {field: [] for field in CHECKED_FIELDS}
    for role, rows in by_role.items():
        if role == "policy_officer":
            continue
        for row in rows:
            for field in CHECKED_FIELDS:
                if row.get("answer", {}).get(field) != baseline[row["id"]].get(field):
                    moved[field].append({"enquiry": row["id"], "role": role})
    return moved


def print_report(by_role: dict[str, list[dict[str, Any]]], movements: dict[str, Any]) -> None:
    print("=== Sublab Easy: four roles, same records/rule/enquiries ===")
    for role, rows in by_role.items():
        print(f"\n[{role}]")
        print(f"{'id':<6}{'decision':<13}{'parsed':<9}{'schema':<9}{'expected':<10}")
        for row in rows:
            print(f"{row['id']:<6}{str(row.get('answer', {}).get('decision', 'ERROR')):<13}"
                  f"{str(row['parsed']):<9}{str(row['schema_valid']):<9}{str(row['agrees_expected']):<10}")
        print("totals: parsed=%d/10 schema-valid=%d/10 expected=%d/10" % (
            sum(row["parsed"] for row in rows), sum(row["schema_valid"] for row in rows),
            sum(row["agrees_expected"] for row in rows)))
    print("\n[field movements relative to policy_officer]")
    for field, changes in movements.items():
        shown = ", ".join(f"{x['enquiry']} ({x['role']})" for x in changes) or "none"
        print(f"{field}: {shown}")


def main() -> None:
    records = read_json(DATA / "records.json")
    policy = read_json(DATA / "policy.json")
    enquiries = read_json(DATA / "enquiries.json")
    by_role = {role: run_role(role, records, policy, enquiries) for role in ROLE_INSTRUCTIONS}
    report = {"roles": by_role, "movements": field_movements(by_role)}
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    (out / "easy_run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(by_role, report["movements"])
    print("\nwrote outputs/easy_run.json")


if __name__ == "__main__":
    main()
