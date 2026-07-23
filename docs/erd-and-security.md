# Sheria Yangu — ERD (DBML for dbdiagrams.io) & Security Architecture
**For the mentor conversation on database design and pseudo-anonymization**

---

## 1. Paste this into dbdiagrams.io

```dbml
Table identity {
  id uuid [pk, note: 'internal only, never exposed via any API response']
  phone_hash varchar [unique, not null, note: 'HMAC-SHA256 of phone number, keyed with a server-side pepper stored outside the DB']
  email_encrypted varchar [null, note: 'present only if user opts into email notifications; encrypted at rest, not hashed, because it must be sendable']
  notify_sms boolean [default: false]
  notify_email boolean [default: false]
  constituency varchar [note: 'self-reported at registration, not verified against the voter roll']
  token uuid [unique, not null, note: 'randomly generated, NOT derived from phone_hash or email — this is the pseudonymous public identifier']
  created_at timestamp
}

Table bills {
  id uuid [pk]
  title varchar
  level varchar [note: 'national | county']
  source_url varchar [note: 'Kenya Law or county assembly, official document only']
  status varchar [note: 'open | closed']
  opens_at timestamp
  closes_at timestamp
  previous_version_id uuid [null, note: 'FK to bills.id — prior year equivalent Act, for comparison summaries']
}

Table clauses {
  id uuid [pk]
  bill_id uuid [not null]
  clause_number varchar
  raw_text text
  summary_en text
  summary_sw text
  previous_clause_id uuid [null, note: 'FK to clauses.id — matching clause in the prior bill version, used for the comparison line in the summary']
  source_url varchar
}

Table responses {
  id uuid [pk]
  token uuid [not null, note: 'FK to identity.token — this table NEVER stores phone_hash, email, or any identity field directly']
  clause_id uuid [not null]
  vote varchar [note: 'kubali | kataa']
  constituency_snapshot varchar [note: 'copied at time of vote from identity.constituency — a static snapshot, not a live join, so analytics never re-touches identity']
  created_at timestamp
}

Table memoranda {
  id uuid [pk]
  token uuid [not null]
  bill_id uuid [not null]
  draft_text text
  edited_text text [null]
  consent_read_summary boolean [not null]
  consent_not_bot boolean [not null]
  consent_terms boolean [not null]
  sent_at timestamp [null]
  status varchar [note: 'draft | sent | failed']
}

Table notification_log {
  id uuid [pk]
  token uuid [not null]
  bill_id uuid [not null]
  channel varchar [note: 'inapp | sms | email']
  identity_joined boolean [note: 'true only if this run read the identity table — the fact this column exists is itself the audit trail']
  sent_at timestamp
}

Ref: responses.clause_id > clauses.id
Ref: clauses.bill_id > bills.id
Ref: memoranda.bill_id > bills.id
Ref: notification_log.bill_id > bills.id
Ref: clauses.previous_clause_id > clauses.id
Ref: bills.previous_version_id > bills.id
```

**Note on `responses.token` and `memoranda.token` and `notification_log.token`:** these aren't drawn as formal foreign keys to `identity.token` in the DBML above on purpose — dbdiagrams will still let you add `Ref: responses.token > identity.token` if your mentor wants the formal constraint visible on the diagram. I left it as a soft reference in the notes so the diagram visually shows what a determined reviewer should notice: `identity` sits in its own box, connected to everything else only through one column, and only `notification_log` legitimately reads across that connection in normal application code.

---

## 2. Answering your mentor's specific concerns, in order

### "An encrypted authorization token for data flowing through the database"
This is a different token from the pseudonymization `token` above — don't conflate them. Your mentor is describing **session authentication**: when a user logs in, issue a signed token (a JWT is the standard choice) that the app presents on every API call to prove "this request comes from a legitimate, currently-logged-in session." That JWT should be signed (so it can't be forged) and short-lived (so a stolen one expires quickly). Separately, all traffic should run over HTTPS (TLS) so the token can't be intercepted in transit, and the `identity` table's sensitive columns (`email_encrypted` especially) should be encrypted at rest in the database, not just access-controlled. Three different protections, often confused as one: **transport encryption** (HTTPS), **authentication tokens** (JWT, proves who's asking), and **anonymization tokens** (the `token` column, decouples identity from activity). Your mentor is asking you to have all three, not just one.

### "The analytics dashboard should show that a verified person participated, but not who"
This is exactly what `responses.constituency_snapshot` does — county analytics is `COUNT(*) GROUP BY constituency_snapshot` against the `responses` table, which never contains a phone number, email, or token-to-identity lookup. The dashboard code should never have a code path that queries `identity` at all.

### "Pseudo-anonymization" (the correct term — not "sudo anonymization")
This is the right word for what you're building, and you should use it deliberately in front of a technical mentor rather than "anonymous" or "zero-knowledge." True anonymization is irreversible; pseudonymization means the link *could* technically be reconstructed by whoever controls both tables plus the pepper key, but it's deliberately walled off, minimized, and audited. That's a real, respected, GDPR-recognized category — say the word correctly and you'll sound like you know exactly what you built, not like you're overselling it.

### National ID number — should you collect it?
**Recommendation: no, not yet.** Here's the reasoning to bring back to your mentor: Kenya's SIM registration rules already require a valid ID to obtain a phone number, so a unique, OTP-verified phone number is already a reasonable proxy for "one real registered person" without your app separately touching a national ID number. Collecting the ID number yourselves adds a real cost — under the Data Protection Act, 2019, a national ID number is treated as sensitive personal data requiring stronger justification, security, and likely a data protection impact assessment — while adding **no actual fraud-prevention benefit**, because you have no way to verify an entered ID number against IPRS or the voter roll (that's precisely your #2 resource ask on slide 10 — you've already identified you don't have this access). An unverifiable ID number is worse than no ID number: it creates the appearance of stronger verification than you actually have. Keep phone-hash uniqueness as your one-person-one-vote mechanism now, and treat real ID verification as the Phase 2 item it already is on your resources slide — contingent on getting that GovTech/IPRS mentor.

### Constituency — self-reported or verified?
**Recommendation: self-reported, and say so out loud.** Verifying against the voter roll requires the same IEBC/IPRS access you don't have yet, and building a verification step now would be exactly the kind of scope-creep the judges already flagged as unrealistic for a student build. Self-reported constituency, clearly disclosed as such, is honest and defensible — and it's a second concrete, measurable trade-off you can add to your Responsible Computing slide if you want a stronger answer than most teams will have: "constituency is self-reported, not verified, until voter-roll access is available."

---

## 3. One thing to flag before the mentor conversation goes further

Slide 8 of Catherine's new deck currently says "National ID verifies a real, unique voter, then is replaced by an anonymous token" — but slide 10 of the same deck asks for a "GovTech / IEBC / IPRS mentor — a path to verified identity" as the single most important resource need. Those two slides contradict each other: one claims ID verification already works, the other admits you don't have it. Fix this before the mentor sees both slides side by side — the honest version (phone+OTP now, ID verification as a Phase 2 ask) is consistent across both slides and is what's written above.
