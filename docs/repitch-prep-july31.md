# Sheria Yangu — Re-pitch Prep, 31 July (3:00 target, 3:30 hard stop)

---

## 1. Critique of Catherine's deck — summary (full version in chat)

Biggest issue first: **the persona is broken across the deck.** Slide 2's hook quotes "Jared Nyakundi, a charcoal burner" testifying against the *national* Finance Bill 2023. Slide 3/4's legal case is the *Nairobi County* Finance Act and the Nyabuto High Court petition — a different bill, different court, different person. Slide 11's close just says "Jared," which reads as if it's the same person as slide 2 — it isn't, and the language used ("no lawyer, no government website") only matches the Nyabuto story, not the Nyakundi one. Pick one verified persona and use them everywhere the pitch says "Jared." Nyabuto is the one I've already confirmed against the actual Kenya Law judgment; if you have a real published source for the Nyakundi quote, keep him instead — the risk is running both without reconciling, which is a hole any prepared judge will find in one question.

Other fixes, ranked:
- **Slide 8 (RC) contradicts slide 10.** Slide 8 says "national ID verifies a real, unique voter" as if that's built. Slide 10 asks for a GovTech/IEBC/IPRS mentor as "the one thing that would unblock us most — without it, our clause voting is advisory." You can't claim ID verification works and also say you don't have it. Use the corrected RC language in section 2 below.
- **Slide 7 is a blurry phone-camera photo of a screen**, glare and all — this is the literal "picture of text" problem the cohort feedback warned about. Replace with a clean screen recording or a real exported screenshot before 31 July.
- **Slide 9's dates are already in the past** (Wk1 is 6–12 Jul) relative to a 31 July pitch — update the whole timeline before presenting it.
- **Slide 6's "KES 500–2K" has no label** — a number floating with no unit context reads as a mistake, not a stat. Either caption it (cost per month? per bill?) or cut it.
- **"DeepSeek V4 Flash"** — verify this is the exact, correct model name from your API dashboard before it goes back on a slide; "Flash" is a naming convention from a different provider (Gemini) and mixing vocabulary is the kind of detail a technical mentor catches.
- Slide 2/3 content is otherwise good — the "39.84% youth voters" and "1,080/55M" stats are consistent with what's already verified. Keep them.
- Slide 4's "courts keep finding it unreachable" (plural) implies more than one ruling — soften to singular unless you have a second citable case.

---

## 2. Responsible computing — the one slide to fix before anything else

Replace slide 8 entirely with this (matches the ERD doc and resolves the slide 8 vs. slide 10 contradiction):

**On-slide:**
> Privacy by design — identity (phone, email) and civic activity (votes, memoranda) sit in separate tables, joined only by an automated, logged notification job. Measure: 0 phone/email fields in the votes table; 0 bulk joins in the query log, reviewed weekly.
> Source authentication — every summary links to its Kenya Law/county assembly source. Measure: 100% of summaries carry a verified source URL.
> Trade-off — we don't have verified identity yet (that's our #1 ask). What we have is one-per-phone-number uniqueness, self-reported constituency, and a pseudonymous token that keeps votes and identity apart except for outbound notifications.

**Narration (~25s):** *"Identity and civic activity live in separate tables, connected only by a token. We don't yet have verified voter identity — that's genuinely our biggest ask, on the next slide. What we do have: one account per phone number, and a notification process that's the only thing allowed to reconnect a token to a contact method, logged every time it runs."*

---

## 3. Condensed script — 3:00 target, ~3:22 with buffer, hard stop 3:30

Simpler sentences throughout, same content, half the words.

**Cold open — 0:10 (Violet):** "Meet [persona — confirm Nyabuto or a sourced alternative]. Nairobi raised fees on boda bodas, taxis, alcohol licences. He asked why. No answer was published. So he went to the High Court to get one."

**Slide 2 — 0:20 (Violet):** "Parliament's 2023 Finance Bill had a 9-day comment window. The Supreme Court upheld it as lawful. Out of 55 million Kenyans, 1,080 sent a memorandum. Lawful on paper. Almost no one could take part."

**Slide 3 — 0:25 (Violet):** "Nairobi's own Finance Act raised the same kind of fees. The county held forums — but showed fee lists, never the cost reasoning behind them. The High Court struck it down last June. Nairobi's next Finance Bill is already at the County Assembly. Same gap, about to repeat."

**Slide 4 — 0:15 (Catherine):** "Sheria Yangu: notify when a bill opens, translate it clause by clause, turn your answer into a memorandum Parliament receives."

**Slide 5 — 0:20 (Catherine):** "Five steps: bill detected, notification sent, AI summarises, you vote per clause, memorandum sent. Every step already runs end to end."

**Slide 6 — 0:20 (Catherine):** "47 counties. 9-day windows. 87-page bills. No human team moves that fast. Our model reads a clause, returns a plain Swahili and English summary, in seconds — cached once, reused for everyone."

**Slide 7 — 0:25 (Both):** narrate the actual demo recording moment by moment — "clause going in, summary coming back, vote recorded, memorandum drafted."

**Slide 8 — 0:25 (Violet):** RC narration from section 2 above.

**Slide 9 — 0:15 (Catherine):** "Violet owns frontend and the scraper. Catherine owns backend and notifications. [State this week's actual status, not the old dates.]"

**Slide 10 — 0:12 (Violet):** "Five asks. The one that matters most: a path to verified identity. Without it, our votes are advisory. With it, Parliament has to take them seriously."

**Slide 11 — 0:15 (Violet):** "[Persona] doesn't need a courtroom next time. A notification, a plain-language clause, a response before the deadline. The right to participate shouldn't require a lawyer. It should require a notification."

**Total: ~3:22.** Rehearse with a stopwatch — this has 8 seconds of margin before the hard stop, which is tight, so trimming the cold open to one sentence is the first cut to make if you run long.

---

## 4. Scoresheet coverage checklist

| Rubric item | Covered? | Where / note |
|---|---|---|
| General problem + stat | Yes | Slide 2, national stat, now accurately sourced |
| Specific problem | Yes | Slide 3, Nairobi case, corrected to the real legal basis |
| Target user + why | Yes | Slide 3 target user box |
| Story hook | Partial | Present but persona is inconsistent — fix before this counts fully |
| Democratic problem is real | Yes | Slide 3 legal barrier framing |
| AI is the right lever | Yes | Slide 6, 47-counties/9-day-window line |
| Alignment explicit & convincing | Partial | Present in script but not yet on Catherine's slide 6 — say it aloud regardless |
| End-to-end solution logic | Yes | Slide 5 |
| AI component explained | Yes | Slide 6, POST /api/summarize + /api/memorandum shown |
| Appropriateness of AI | Yes | Old-way-vs-Sheria-Yangu comparison |
| Data for the AI | Partial | Source named (Kenya Law/county sites) but not explicitly said aloud — add one line |
| Problem-to-solution mapping | Yes | Slide 4 |
| Something real is shown | Partial | Slide 7 currently a blurry photo — needs a real recording |
| Builders narrate over it | Depends on rehearsal | Script section above covers it — must be delivered, not read |
| Demo matches the solution | Partial | Confirm the recording shows notify → summary → vote → memo → sent, all five |
| Clarity & production quality | No | Fix the slide 7 image quality first |
| Fits window & embedded | Confirm | Must be ~20–25s and inside the deck, not a separate link |
| Remaining components listed | Yes | Slide 9 |
| Realistic sequencing | Yes | Slide 9, though dates need updating |
| Scope honesty | Yes | "Advisory until verified identity" framing on slide 10 is honest |
| Definition of usable product | Yes | "A real citizen, a real bill, a real memorandum sent" |
| Ownership & roles | Yes on slide, must also be said aloud | Slide 9 — say it in the pitch too, this was your worst score last time |
| Clear RC integration | Partial | Fix slide 8 per section 2 |
| Trade-off awareness | Partial | Current trade-off (coordinated fraud) is real but secondary — lead with the identity-verification trade-off instead |
| Measurable RC consideration | Partial | Slide 8 has a "zero PII fields, audited weekly" line — keep it, make sure it's said aloud |
| Credible, appropriate data use | Yes | Kenya Law/county assembly sourcing |
| Specific asks | Yes | Slide 10, five named asks |
| Actionability | Yes | Mostly realistic; GovTech mentor ask is the most actionable one |
| Presentation chemistry | Depends on rehearsal | Not a content issue |
| Confidence | Depends on rehearsal | Not a content issue |
| Clarity & pace | Depends on rehearsal | Rehearse against the 3:00 script above with a stopwatch |
| Slide quality | Partial | Fix slide 7 photo, slide 6 unlabeled figure, verify model name |
| Progression & visual engagement | Yes, once slide 7 is fixed | — |
| Storytelling arc carried through | No, until persona is fixed | This is the single most important fix on this whole list |
| Powerful close | Yes, if delivered with a pause | Slide 11 line is strong — practice the pause before/after |
| Wow factor | Depends on delivery | Persona + pause at the close are what create this |
| Backing worthiness | Partial | Ownership stated aloud + honest identity-verification ask both help this directly |

---

## 5. API keys — how many do you actually need

**Africa's Talking: one key, one account.** The same API key and username (`sandbox` for now, your live username later) covers both OTP-SMS and bulk SMS notifications — they're just different endpoint calls on the same account, not separate products requiring separate keys.

**Email notifications need a different service — Africa's Talking doesn't offer email.** Cheapest path for a student build: SendGrid's free tier (100 emails/day, enough for a prototype) or Mailgun's free tier. Either needs its own API key, separate from Africa's Talking and separate from DeepSeek.

**Google APIs are only needed for Google Sign-In**, via a free Firebase project — this is unrelated to email delivery. If you skip Google Sign-In and keep phone+OTP as the only login method, you don't need this at all.

So: three credential sets total if you want phone OTP + SMS notifications + email notifications + Google sign-in (Africa's Talking, an email service, Firebase) — not one per feature.

---

## 6. Legal question — are auto-sent/auto-compiled memoranda to Parliament allowed?

I couldn't find a Kenyan statute or case that directly addresses AI-drafted or auto-compiled memoranda — this is genuinely unresolved territory, not something I can confirm either way. What the Constitution and case law are clear on is that public participation memoranda need to reflect the actual views of the person submitting them; nothing in the process legally requires the submission to be hand-typed. The safest design position — and the one your own T&Cs screen already builds toward — is requiring the citizen to explicitly read, optionally edit, and consent to the drafted text before it's sent, rather than sending anything automatically without a human confirmation step. That's good practice regardless of the legal answer, and it's exactly why "legal review" is already your #3 resource ask on slide 10 — keep pushing for that conversation with a real lawyer rather than treating this as settled.

---

## 7. Summarization policy update — add the comparison requirement

Your two-sentence summaries won't hold up against a real 50–90 page bill. Updated policy for the DeepSeek prompt:

Each clause summary must include: (1) a plain-language explanation in English and Swahili, aimed at a 20-year-old reader, (2) the specific number or change involved — fee amounts, percentages, thresholds, not vague language, (3) a comparison line against the equivalent clause in the previous year's Act, where one exists — e.g., "Last year this fee was Sh 700; this bill raises it to Sh 1,000 — a 43% increase," pulled via the `previous_clause_id` link in the ERD schema, (4) a one-line "who this affects" tag (boda boda riders, market vendors, etc.).

The hard part is matching a clause in this year's bill to the equivalent clause in last year's — that's a real engineering problem, not a prompt-engineering one. For the MVP, don't try to automate this matching generally. Manually map the handful of recurring fee categories you already know about (boda boda registration, taxi/app-hailing fees, market levies, alcohol licences, single business permit) between the 2022, 2023, and 2025/26 Nairobi Finance Acts, and only offer the comparison line for those. Anything outside that curated list gets the plain summary without a comparison rather than a fabricated one.
