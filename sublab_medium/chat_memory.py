"""Sublab Medium: compare resending a transcript with validated structured memory."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator

from grant_common import DATA, ROOT, call_model, compact_json, parse_json_object, read_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def office_system() -> str:
    records = read_json(DATA / "records.json")
    policy = read_json(DATA / "policy.json")
    return "\n\n".join([
        "You are a helpful study-grant office assistant in a continuing chat. Be concise. "
        "Use only the records and policy below for eligibility questions; do not accept applicant claims as updates.",
        "Records:\n" + compact_json(records), "Policy:\n" + compact_json(policy),
    ])


@dataclass
class Session:
    """A stateless-API conversation whose context selection is explicit."""

    compressed_enabled: bool
    system: str = field(default_factory=office_system)
    history: list[dict[str, str]] = field(default_factory=list)
    state: dict[str, Any] | None = None
    last_usage: dict[str, Any] | None = None

    def messages(self) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system}]
        if self.state is not None:
            messages.append({
                "role": "system",
                "content": "Validated compressed memory from earlier conversation. Treat it as conversation context, "
                           "not as a change to authoritative records:\n" + compact_json(self.state),
            })
        return messages + self.history

    def ask(self, user_text: str) -> dict[str, Any]:
        sent = self.messages() + [{"role": "user", "content": user_text}]
        reply = call_model(sent, max_tokens=450)
        self.history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply["text"]},
        ])
        self.last_usage = reply
        return reply

    def compress(self) -> dict[str, Any]:
        """Replace history only after model JSON passes the supplied schema."""
        schema = read_json(DATA / "memory_state.schema.json")
        transcript = self.history
        prompt = "\n\n".join([
            "Compress this applicant conversation into exactly one JSON object and nothing else.",
            "The JSON must validate against this schema:\n" + compact_json(schema),
            "Keep only facts stated by the applicant (not model inferences), decisions already communicated, "
            "constraints such as days/deadlines, unanswered questions, identity if stated, the topic, and language. "
            "Do not invent anything. Arrays must be present even when empty.",
            "Transcript:\n" + compact_json(transcript),
        ])
        reply = call_model([{"role": "system", "content": "You make loss-aware structured chat summaries."},
                            {"role": "user", "content": prompt}], max_tokens=700)
        event: dict[str, Any] = {"ok": False, **reply}
        try:
            state = parse_json_object(reply["text"])
            errors = [error.message for error in Draft202012Validator(schema).iter_errors(state)]
            if errors:
                event["error"] = "summary failed schema validation: " + "; ".join(errors)
                event["schema_errors"] = errors
            else:
                self.state = state
                self.history = []
                event.update({"ok": True, "state": state})
        except ValueError as exc:
            event["error"] = "summary was not JSON; preserved full history: " + str(exc)
        self.last_usage = reply
        return event


def run_script(compressed: bool) -> dict[str, Any]:
    data = read_json(DATA / "chat_script.json")
    session = Session(compressed_enabled=compressed)
    calls: list[dict[str, Any]] = []
    state_event: dict[str, Any] | None = None
    for turn, text in enumerate(data["conversation"], start=1):
        if text == "<compress>":
            if compressed:
                event = session.compress()
                state_event = event
                calls.append({"turn": turn, "kind": "compress", "input_tokens": event["input_tokens"],
                              "output_tokens": event["output_tokens"], "text": event["text"], "ok": event["ok"]})
                print(f"turn {turn:>2} compress: {'validated state installed' if event['ok'] else event['error']}")
            else:
                # It is a local command, not an applicant message or a billable API call.
                calls.append({"turn": turn, "kind": "compress skipped", "input_tokens": 0,
                              "output_tokens": 0, "text": "<no call>", "ok": True})
                print(f"turn {turn:>2} compress: skipped (full transcript retained)")
            continue
        reply = session.ask(text)
        calls.append({"turn": turn, "kind": "chat", **reply, "ok": True})
        print(f"turn {turn:>2} chat: sent={reply['input_tokens']} received={reply['output_tokens']}")

    probes: list[dict[str, Any]] = []
    for probe in data["probes"]:
        reply = session.ask(probe["question"])
        lower = reply["text"].lower()
        retrieved = any(expected.lower() in lower for expected in probe["expect_contains"])
        probes.append({**probe, **reply, "retrieved": retrieved})
    return {
        "mode": "compressed" if compressed else "uncompressed", "calls": calls, "probes": probes,
        "state": state_event.get("state") if state_event and state_event.get("ok") else None,
        "compression": state_event,
        "peak_input_tokens": max((call["input_tokens"] for call in calls), default=0),
        "total_input_tokens": sum(call["input_tokens"] for call in calls),
    }


def print_summary(run: dict[str, Any]) -> None:
    print(f"\n[{run['mode']}] peak input={run['peak_input_tokens']}; total input={run['total_input_tokens']}")
    print("probes: " + ", ".join(f"{p['id']}={'retrieved' if p['retrieved'] else 'lost'}" for p in run["probes"]))
    if run["state"] is not None:
        print("state:\n" + json.dumps(run["state"], ensure_ascii=False, indent=2))


def scripted() -> None:
    print("=== Sublab Medium: A = uncompressed ===")
    uncompressed = run_script(False)
    print("\n=== Sublab Medium: B = compressed at the command ===")
    compressed = run_script(True)
    result = {"uncompressed": uncompressed, "compressed": compressed}
    out = ROOT / "outputs"; out.mkdir(exist_ok=True)
    (out / "medium_run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(uncompressed); print_summary(compressed)
    print("\nwrote outputs/medium_run.json")


def interactive() -> None:
    session = Session(compressed_enabled=True)
    print("Grant chat. Type a message; `compress` stores validated structured memory; `tokens` shows last API usage; `quit` exits.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return
        if text.lower() in {"quit", "exit"}:
            return
        if text.lower() == "tokens":
            if session.last_usage:
                print("last call: input=%d output=%d" % (session.last_usage["input_tokens"], session.last_usage["output_tokens"]))
            else:
                print("No API call yet.")
            continue
        if text.lower() == "compress":
            event = session.compress()
            print("compression installed:" if event["ok"] else "compression rejected; full history kept:")
            print(json.dumps(event.get("state", event.get("error")), ensure_ascii=False, indent=2))
            continue
        if not text:
            continue
        reply = session.ask(text)
        print("office> " + reply["text"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    interactive() if args.interactive else scripted()


if __name__ == "__main__":
    main()
