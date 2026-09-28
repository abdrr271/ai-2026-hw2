# HW2 submission

**Name:** Abdrakhman
**Student ID:** not provided
**Group:** not provided
**Repository:** https://github.com/abdrr271/ai-2026-hw2

## AI tool disclosure

I used OpenAI Codex to locate the instructor's public starter repository, implement the three Python programs, review the prompts and schemas, run/debug the programs, and render this evidence from the saved live outputs. The model calls in this submission used OpenRouter's `qwen/qwen3.8-27b` consistently in all three sublabs because the local `.env` supplied an OpenRouter key. I did not commit the key. The model was used for the assignment's required model calls; the tables and totals below were generated from those calls, not invented.

---

## Sublab Easy — one task, four roles

### Decisions per role

Each cell is `decision` followed by whether all four checked structured fields agree with `data/enquiries.json`.

| Enquiry | policy_officer | front_desk | auditor | bilingual_clerk |
|---|---|---|---|---|
| E-01 | granted ✓ | not_found ✗ | not_found ✗ | granted ✓ |
| E-02 | more_info ✓ | more_info ✓ | more_info ✓ | more_info ✓ |
| E-03 | refused ✓ | refused ✓ | refused ✓ | refused ✓ |
| E-04 | refused ✓ | refused ✓ | refused ✓ | refused ✓ |
| E-05 | granted ✓ | granted ✓ | more_info ✗ | granted ✓ |
| E-06 | granted ✓ | granted ✓ | refused ✗ | granted ✓ |
| E-07 | granted ✓ | granted ✓ | granted ✓ | granted ✓ |
| E-08 | not_found ✓ | not_found ✓ | not_found ✓ | not_found ✓ |
| E-09 | refused ✓ | refused ✓ | refused ✓ | refused ✓ |
| E-10 | more_info ✓ | more_info ✓ | more_info ✓ | refused ✗ |
| **agrees with `expected`** | 10/10 | 9/10 | 7/10 | 9/10 |
| **parsed** | 10/10 | 10/10 | 10/10 | 10/10 |
| **schema-valid** | 10/10 | 10/10 | 10/10 | 10/10 |

### Which field moved, on which enquiry, under which role

| Field | Enquiries that moved | Role(s) that moved it |
|---|---|---|
| `found` | E-01 | auditor, front_desk |
| `decision` | E-01, E-05, E-06, E-10 | auditor, bilingual_clerk, front_desk |
| `amount` | E-01, E-05, E-06 | auditor, front_desk |
| `missing_documents` | none | none |

`missing_documents` moved on no enquiry in this run.

### Raw replies

Full reply for an enquiry where `front_desk` changed the policy officer's decision (E-01):

```json
{
  "applicant_id": "A-201",
  "found": false,
  "decision": "not_found",
  "amount": 0,
  "missing_documents": [],
  "reason": "No applicant record exists for ID A-201. Please verify your official applicant ID with the registrar's office."
}
```

E-07 from the bilingual clerk:

```json
{
  "applicant_id": "A-201",
  "found": true,
  "decision": "granted",
  "amount": 250000,
  "missing_documents": [],
  "reason": "Сіздің GPA-ңыз (3.4) 2.67-ден жоғары, табыс деңгейіңіз 1-ші санатта және қажетті құжаттар (транскрипт және жеке куәлік) толық. Сондықтан сізге 250 000 теңге көлемінде грант беріледі."
}
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
| 1 | 613 | 613 |
| 2 | 799 | 661 |
| 3 | 903 | 778 |
| 4 | 987 | 856 |
| 5 | 1049 | 911 |
| 6 | 1165 | 1016 |
| 7 | 1283 | 1085 |
| 8 | 1365 | 1176 |
| 9 | 1445 | 1240 |
| 10 | 0 | 1050 |
| 11 | 1565 | 772 |
| 12 | 1629 | 853 |
| **peak** | **1629** | **1240** |
| **total for the run** | **12803** | **11011** |

### Probes after the conversation

| Probe | Tests | A retrieved? | A answer | B retrieved? | B answer |
|---|---|---|---|---|---|
| Q-1 | identity, stated once in turn 1 | yes | You are **Daniyar Qoshan**, and your applicant number is **A-202**. | yes | You are **Daniyar Qoshan**, and your applicant ID is **A-202**. |
| Q-2 | the missing document, turn 5 | yes | The **ID card** is still missing from your file. | yes | The **ID card** is still missing from your file. |
| Q-3 | the band from turn 3 and the amount from turn 4 | yes | Your income band is **2**, which corresponds to a grant amount of **150,000 KZT**. | yes | Your income band is **2**, which corresponds to a grant amount of **150,000 KZT**. |
| Q-4 | a constraint the applicant stated in turn 6 and never repeated | yes | You mentioned that you can come to the office on **Thursdays**. | yes | You can come to the office on **Thursdays**. |
| Q-5 | an open question, turn 7, never answered | yes | You asked if a scanned letter from your employer would count as a required document. I informed you that the policy requires an ID card, and an employer letter is not an acceptable substitute. | yes | You asked if a scanned letter from an employer counts, or if it has to be the original. |
| **retrieved** | | **5/5** | | **5/5** | |

### The state my compression produced

```json
{
  "applicant_id": "A-202",
  "topic": "Study grant application eligibility and document submission",
  "facts": [
    "Applicant name is Daniyar Qoshan",
    "Transcript was sent last week",
    "Income band is 2",
    "Family's certificate confirms income band is 2",
    "Scanner at home broke, preventing ID card upload",
    "Sister Aruzhan applied last year and is on file"
  ],
  "decisions": [],
  "constraints": [
    "Can only come to the office on Thursdays",
    "Has lab all week otherwise"
  ],
  "open_questions": [
    "Does a scanned letter from an employer count, or does it have to be the original?",
    "If the ID card is brought on Thursday, will the decision be made the same day?"
  ],
  "language": "English"
}
```

### Written answers

**1. What did compression buy?**

It cut the peak from 1629 to 1240 input tokens and the scripted-run total from 12803 to 11011. Retrieval was 5/5 without compression and 5/5 with it, so no probe was lost in this run. This is not proof that summaries never lose facts; it shows this particular structured state retained the five tested facts.

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
| story-01 | yes | yes | none | none |
| story-02 | yes | yes | graduation_year, gpa_4_scale, gpa_original | no GPA stated |
| story-03 | yes | yes | none | non-4.0 GPA; unpublished paper |
| story-04 | yes | yes | none | unpublished paper |
| story-05 | yes | yes | none | unpublished paper |
| story-06 | yes | yes | graduation_year, gpa_4_scale, gpa_original | unpublished paper; contradiction |

The four traps, for reference: no GPA stated · a GPA on another scale · a paper that is not published · a story that contradicts itself.

Extraction for story-06:

```json
{
  "candidate_id": "story-06",
  "full_name": "Nurzhan Abilov",
  "degree": "BSc in Statistics",
  "graduation_year": null,
  "gpa_4_scale": null,
  "gpa_original": null,
  "languages": [
    "Kazakh",
    "Russian",
    "English"
  ],
  "published_peer_reviewed_outputs": 1,
  "nonpublished_outputs": [
    "One poster at a local event"
  ],
  "relevant_experience_months": 40,
  "uncounted_experience": [],
  "evidence": {
    "full_name": [
      "Nurzhan Abilov"
    ],
    "degree": [
      "I graduated in 2024 with a BSc in Statistics."
    ],
    "languages": [
      "Languages: Kazakh, Russian, English."
    ],
    "published_peer_reviewed_outputs": [
      "one paper published, in a peer-reviewed proceedings"
    ],
    "nonpublished_outputs": [
      "One poster at a local event, which I do not think counts."
    ],
    "relevant_experience_months": [
      "I have been at an insurance analytics team since February 2023, which is about forty months."
    ]
  },
  "ambiguities": [
    "GPA: 'My GPA was 3.2. Actually I should double-check that, I think it was 3.5'",
    "Graduation Year: 'I graduated in 2024' vs 'I am currently a final-year student graduating in 2026'"
  ]
}
```

### Part 2 — scores and the winner

| Candidate | academic (0–5) | research (0–5) | experience (0–5) | weighted total (code) |
|---|---|---|---|---|
| story-01 | 5 | 5 | 2 | 4.4 |
| story-02 | 0 | 0 | 5 | 1.0 |
| story-03 | 4 | 3 | 4 | 3.7 |
| story-04 | 4 | 2 | 5 | 3.6 |
| story-05 | 5 | 2 | 3 | 3.7 |
| story-06 | 0 | 1 | 5 | 1.3 |

**Winner, computed by my code:** `story-01` with `4.40`.

**The model's prose answer, asked separately (“who should win?”):**

> Based on the provided rubric and extracted records, **Aziza Bekova (story-01)** is the recommended candidate to receive the funded scholarship.
>
> Here is the concise prose recommendation:
>
> Aziza Bekova presents the strongest overall profile, achieving a weighted total of **3.80**. Her academic record is robust, with a clearly stated GPA of 3.8/4.0, which meets the threshold for a high score on the academic criterion (weight 0.5). Furthermore, she is the only candidate with two confirmed peer-reviewed publications, securing a perfect score on the research criterion (weight 0.3). While her relevant experience of eight months is modest compared to other candidates, her superior academic and research outputs outweigh this limitation.
>
> In comparison, Dias Yerzhanov (story-02) has the most extensive experience (36 months) but lacks any stated academic record or publications, resulting in a lower weighted total. Tamerlan Saparov (story-04) and Lyazzat Omarova (story-03) have strong profiles but fall short of Bekova’s combination of high GPA and multiple publications. Nurzhan Abilov (story-06) is disqualified from a clear ranking due to contradictory statements regarding his GPA and graduation year, which the rubric dictates should result in null scores for those fields. Therefore, Aziza Bekova is the most deserving recipient.

### Part 3 — written answers

**1. Which rule did you have to add, and what broke without it?**

I added a representation-normalization rule before validation: a single evidence quote is stored as a one-element quote list, and a model response that separates original GPA value and scale is stored as `value / scale`. Story-01 forced it: the model gave valid evidence but a scalar quote/GPA object on an early response, which otherwise failed the strict record schema despite containing the required facts. The underlying extraction rule still remains strict: absent facts are null and contradictions are not repaired.

**2. Where did the model guess, and where did your code have to decide?**

The model made a subjective rubric judgement when it assigned story-01 experience `2/5` for its stated eight months. Code, not the model, multiplied the three scores by 0.5, 0.3, and 0.2, rounded to two decimals, sorted them, and selected story-01 at 4.40. The code also retained null GPA and graduation year for story-06 rather than averaging contradictory claims.

**3. Did your prose ranking and your computed ranking agree?**

They agree on story-01 / Aziza Bekova, but I trust the computed ranking more. The prose reply even states a weighted total of 3.80 while the actual fields and code produce 4.40; that mismatch is exactly why prose alone is not a comparable ranking artifact. I would require structured per-criterion scores, evidence links, and deterministic arithmetic before trusting prose alone.

**4. The rubric has no anchor for a contradicted field. What did you do and what should the rule be?**

For story-06, I set GPA and graduation year to null and listed both conflicting claims in `ambiguities`; its academic score was consequently 0 in this run. The policy should explicitly say that a material contradiction produces “needs verification” and either a zero/withheld score until documents resolve it, rather than letting a model choose the more favorable number.

**5. How close were your top two candidates?**

The top two are `story-01` at 4.40 and `story-03` at 3.70, a difference of 0.70; this is not within 0.05. If it were within 0.05, I would tell the committee it is effectively tied and re-check source quotations, date overlap, publication status, GPA scale conversion, and score anchors before choosing a winner.

---

## Reflection

Reliable model output needs more than asking for JSON: the prompt establishes a contract, the program validates it, and critical outcomes remain code-owned. The Easy role errors and the prose-total mismatch show why a plausible natural-language answer is not enough.
