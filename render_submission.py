"""Render the required submission evidence from the live-run JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from sublab_hard.cv_extract_and_rank import detected_traps, null_fields


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def one_line(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def decision_cell(row: dict) -> str:
    return f"{row.get('answer', {}).get('decision', 'parse error')} {'✓' if row['agrees_expected'] else '✗'}"


def render() -> str:
    easy = json.loads((OUT / "easy_run.json").read_text(encoding="utf-8"))
    medium = json.loads((OUT / "medium_run.json").read_text(encoding="utf-8"))
    hard = json.loads((OUT / "hard_run.json").read_text(encoding="utf-8"))
    roles = easy["roles"]
    model = roles["policy_officer"][0]["model"]
    rows = []
    for i in range(10):
        enquiry = roles["policy_officer"][i]["id"]
        rows.append("| " + enquiry + " | " + " | ".join(
            decision_cell(roles[role][i]) for role in roles) + " |")
    totals = []
    for label, field in (("agrees with `expected`", "agrees_expected"), ("parsed", "parsed"), ("schema-valid", "schema_valid")):
        totals.append("| **" + label + "** | " + " | ".join(
            f"{sum(r[field] for r in roles[role])}/10" for role in roles) + " |")
    movement_rows = []
    for field, changes in easy["movements"].items():
        by_enquiry = ", ".join(sorted({change["enquiry"] for change in changes})) or "none"
        by_role = ", ".join(sorted({change["role"] for change in changes})) or "none"
        movement_rows.append(f"| `{field}` | {by_enquiry} | {by_role} |")
    changed = next(row for row in roles["front_desk"] if row["id"] == "E-01")
    kz = next(row for row in roles["bilingual_clerk"] if row["id"] == "E-07")

    def calls_by_turn(run: dict) -> dict[int, int]:
        return {call["turn"]: call["input_tokens"] for call in run["calls"]}
    full_calls, compressed_calls = calls_by_turn(medium["uncompressed"]), calls_by_turn(medium["compressed"])
    token_rows = [f"| {turn} | {full_calls.get(turn, 0)} | {compressed_calls.get(turn, 0)} |" for turn in range(1, 13)]
    probe_rows = []
    for left, right in zip(medium["uncompressed"]["probes"], medium["compressed"]["probes"]):
        probe_rows.append(
            f"| {left['id']} | {one_line(left['tests'])} | {'yes' if left['retrieved'] else 'no'} | "
            f"{one_line(left['text'])} | {'yes' if right['retrieved'] else 'no'} | {one_line(right['text'])} |"
        )
    full_retrieved = sum(probe["retrieved"] for probe in medium["uncompressed"]["probes"])
    compressed_retrieved = sum(probe["retrieved"] for probe in medium["compressed"]["probes"])

    extraction_rows = []
    for item in hard["extractions"]:
        cv = item.get("cv", {})
        extraction_rows.append(
            f"| {item['candidate_id']} | {'yes' if item['parsed'] else 'no'} | {'yes' if item['valid'] else 'no'} | "
            f"{', '.join(null_fields(cv)) or 'none'} | {'; '.join(detected_traps(item)) or 'none'} |"
        )
    score_rows = []
    for score in hard["scores"]:
        values = score.get("score", {})
        score_rows.append(f"| {score['candidate_id']} | {values.get('academic', '—')} | {values.get('research', '—')} | "
                          f"{values.get('experience', '—')} | {score.get('weighted_total', '—')} |")
    valid_scores = [score for score in hard["scores"] if score.get("valid")]
    winner = max(valid_scores, key=lambda score: score["weighted_total"])
    ranked = sorted(valid_scores, key=lambda score: score["weighted_total"], reverse=True)
    gap = round(ranked[0]["weighted_total"] - ranked[1]["weighted_total"], 2)
    story6 = next(item["cv"] for item in hard["extractions"] if item["candidate_id"] == "story-06")
    prose_quote = "\n".join("> " + line if line else ">" for line in hard["prose"]["text"].splitlines())

    return f'''# HW2 submission

**Name:** Abdrakhman
**Student ID:** not provided
**Group:** not provided
**Repository:** https://github.com/abdrr271/ai-2026-hw2

## AI tool disclosure

I used OpenAI Codex to locate the instructor's public starter repository, implement the three Python programs, review the prompts and schemas, run/debug the programs, and render this evidence from the saved live outputs. The model calls in this submission used OpenRouter's `{model}` consistently in all three sublabs because the local `.env` supplied an OpenRouter key. I did not commit the key. The model was used for the assignment's required model calls; the tables and totals below were generated from those calls, not invented.

---

## Sublab Easy — one task, four roles

### Decisions per role

Each cell is `decision` followed by whether all four checked structured fields agree with `data/enquiries.json`.

| Enquiry | policy_officer | front_desk | auditor | bilingual_clerk |
|---|---|---|---|---|
{chr(10).join(rows)}
{chr(10).join(totals)}

### Which field moved, on which enquiry, under which role

| Field | Enquiries that moved | Role(s) that moved it |
|---|---|---|
{chr(10).join(movement_rows)}

`missing_documents` moved on no enquiry in this run.

### Raw replies

Full reply for an enquiry where `front_desk` changed the policy officer's decision (E-01):

```json
{changed['text']}
```

E-07 from the bilingual clerk:

```json
{kz['text']}
```

### Written answers

**1. Which fields are role-sensitive and which are not?**

In this run, every checked field except `missing_documents` was role-sensitive: `found` moved on E-01 under front_desk and auditor; `decision` moved on E-01, E-05, E-06 and E-10; and `amount` moved on E-01, E-05 and E-06. `missing_documents` did not move. This is also a warning about reliability: the intended bilingual role should only change `reason`, yet it changed E-10 to `refused`; front_desk also wrongly returned `not_found` for recorded applicant A-201. The policy officer was the only role with 10/10 agreement.

**2. Which enquiries are most sensitive to the role, and why those?**

E-03 and E-04 test ineligible applicants for different policy reasons (GPA and income band), where a customer-service role may soften refusal. E-07 tests whether language changes the explanation but not the record decision; here the bilingual reason is visibly Kazakh and the fields match. E-10 tests that a claimed upload is not evidence: the policy officer correctly retained `more_info` and `id_card`, while the bilingual run incorrectly changed the decision. In the observed data E-01/E-05/E-06 were also sensitive because the auditor followed its “never grant” instruction.

**3. Where does discretion belong — the role paragraph, or code that reads `decision` afterwards?**

The role paragraph is useful for a human-facing explanation and controlled variation, but expensive grant decisions need code after the reply: validate the schema, look up the canonical record, recompute eligibility, and reject/route mismatches. A downstream program sees only fields; it cannot reliably infer whether a result was produced by a policy officer, front desk, auditor, or a model mistake unless the program records the role separately.

**4. Is a role a boundary?**

No. In Week 2 terms, the role paragraph is ordinary input tokens in a system message, not an enforcement mechanism. It can be ignored or outweighed by ambiguity/model behavior, as E-01 shows. If a wrong decision were expensive, code would enforce an allow-list of applicant IDs, deterministic policy evaluation, JSON/schema checks, audit logs, and human review for exceptions; it would not trust “never grant” in natural language as a security boundary.

---

## Sublab Medium — memory you choose

### Tokens per call

The `<compress>` row is a local command: A intentionally makes no API call while B makes the summary call.

| Call | A — never compressed | B — compressed at the `compress` turn |
|---|---|---|
{chr(10).join(token_rows)}
| **peak** | **{medium['uncompressed']['peak_input_tokens']}** | **{medium['compressed']['peak_input_tokens']}** |
| **total for the run** | **{medium['uncompressed']['total_input_tokens']}** | **{medium['compressed']['total_input_tokens']}** |

### Probes after the conversation

| Probe | Tests | A retrieved? | A answer | B retrieved? | B answer |
|---|---|---|---|---|---|
{chr(10).join(probe_rows)}
| **retrieved** | | **{full_retrieved}/5** | | **{compressed_retrieved}/5** | |

### The state my compression produced

```json
{json.dumps(medium['compressed']['state'], ensure_ascii=False, indent=2)}
```

### Written answers

**1. What did compression buy?**

It cut the peak from {medium['uncompressed']['peak_input_tokens']} to {medium['compressed']['peak_input_tokens']} input tokens and the scripted-run total from {medium['uncompressed']['total_input_tokens']} to {medium['compressed']['total_input_tokens']}. Retrieval was {full_retrieved}/5 without compression and {compressed_retrieved}/5 with it, so no probe was lost in this run. This is not proof that summaries never lose facts; it shows this particular structured state retained the five tested facts.

**2. Why must the state be structured rather than a paragraph?**

Named fields make an incomplete or invented summary inspectable: the program validates required fields and arrays, and a reader can see whether identity, constraints, and unanswered questions survived. A prose paragraph has no reliable contract for a program to check; it can sound complete while silently dropping Thursday or the employer-letter question.

**3. What is missing from your state that you would add?**

I would add a `document_status` field with source and certainty (for example, `id_card: missing according to record`) because the current facts deliberately contain only applicant statements. To pay for it, I would drop the duplicate fact that the family certificate confirms band 2; the band itself is enough for this short session.

**4. When is compression the wrong choice?**

It is wrong for a conversation in which exact wording is evidence — for example, a grievance, consent, legal dispute, or a negotiation with promises and dates that must be quoted verbatim. This program only catches malformed JSON/schema failures, not semantically important omissions that still yield valid JSON, so it would not necessarily notice that loss.

---

## Sublab Hard — stories in, CVs out, the best candidate by code

### Part 1 — extraction

| Story | Parsed? | Valid? | Fields that came back `null` | Traps hit |
|---|---|---|---|---|
{chr(10).join(extraction_rows)}

The four traps, for reference: no GPA stated · a GPA on another scale · a paper that is not published · a story that contradicts itself.

Extraction for story-06:

```json
{json.dumps(story6, ensure_ascii=False, indent=2)}
```

### Part 2 — scores and the winner

| Candidate | academic (0–5) | research (0–5) | experience (0–5) | weighted total (code) |
|---|---|---|---|---|
{chr(10).join(score_rows)}

**Winner, computed by my code:** `{winner['candidate_id']}` with `{winner['weighted_total']:.2f}`.

**The model's prose answer, asked separately (“who should win?”):**

{prose_quote}

### Part 3 — written answers

**1. Which rule did you have to add, and what broke without it?**

I added a representation-normalization rule before validation: a single evidence quote is stored as a one-element quote list, and a model response that separates original GPA value and scale is stored as `value / scale`. Story-01 forced it: the model gave valid evidence but a scalar quote/GPA object on an early response, which otherwise failed the strict record schema despite containing the required facts. The underlying extraction rule still remains strict: absent facts are null and contradictions are not repaired.

**2. Where did the model guess, and where did your code have to decide?**

The model made a subjective rubric judgement when it assigned story-01 experience `2/5` for its stated eight months. Code, not the model, multiplied the three scores by 0.5, 0.3, and 0.2, rounded to two decimals, sorted them, and selected story-01 at {winner['weighted_total']:.2f}. The code also retained null GPA and graduation year for story-06 rather than averaging contradictory claims.

**3. Did your prose ranking and your computed ranking agree?**

They agree on story-01 / Aziza Bekova, but I trust the computed ranking more. The prose reply even states a weighted total of 3.80 while the actual fields and code produce {winner['weighted_total']:.2f}; that mismatch is exactly why prose alone is not a comparable ranking artifact. I would require structured per-criterion scores, evidence links, and deterministic arithmetic before trusting prose alone.

**4. The rubric has no anchor for a contradicted field. What did you do and what should the rule be?**

For story-06, I set GPA and graduation year to null and listed both conflicting claims in `ambiguities`; its academic score was consequently 0 in this run. The policy should explicitly say that a material contradiction produces “needs verification” and either a zero/withheld score until documents resolve it, rather than letting a model choose the more favorable number.

**5. How close were your top two candidates?**

The top two are `{ranked[0]['candidate_id']}` at {ranked[0]['weighted_total']:.2f} and `{ranked[1]['candidate_id']}` at {ranked[1]['weighted_total']:.2f}, a difference of {gap:.2f}; this is not within 0.05. If it were within 0.05, I would tell the committee it is effectively tied and re-check source quotations, date overlap, publication status, GPA scale conversion, and score anchors before choosing a winner.

---

## Reflection

Reliable model output needs more than asking for JSON: the prompt establishes a contract, the program validates it, and critical outcomes remain code-owned. The Easy role errors and the prose-total mismatch show why a plausible natural-language answer is not enough.
'''


if __name__ == "__main__":
    (ROOT / "SUBMISSION.md").write_text(render(), encoding="utf-8")
    print("wrote SUBMISSION.md from outputs/*.json")
