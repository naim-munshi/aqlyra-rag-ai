# Study Abroad — Student Journey v1 (draft, isolated branch)

## Product goals
Provide an owner-private workflow from student background to university discovery,
admissions, scholarship research, document readiness, government visa rules and
embassy/consulate research. **Not an immigration lawyer, application representative,
licensed adviser or embassy booking agent.** Never imply automatic eligibility,
admission, official appointments, or visa approval.

## Implementation status
- `/study-abroad` authenticated Next.js workspace and chat **+** menu entry.
- First-class `/api/v1/study-abroad` backend routes; student cases/checklists, 
  linked documents and dated research reports persist in PostgreSQL.
- Workflow registry isolates the **student** path and reserves **job** as
  disabled, separate future option. No fake job visa guidance is exposed.
- Student profile uses nationality/citizenship, *current residence*,
  destination, intended degree, subject and intake. It stores **no passport
  number, birth date, bank balance or submitted visa forms**.
- Suggested checklist items default to `needs_verification`, NOT legally required.
  Each item's manual state and HTTPS evidence URL can be recorded.
- User uploads through the EXISTING protected file-processing backend;
  document link is accepted **only if owned by the authenticated user and
  status=ready**. Removing a case does not delete the original uploaded files.
- University, admission, scholarship, student visa, embassy and predeparture
  topics use the existing opt-in Tavily source-search/extraction + configured
  LLM. Prompt uses only case profile, **never file bodies**.
- Each report stores dated answer and source snapshot. `verification_status`
  is always `needs_official_verification`. Official government/university
  URLs should be opened by the student and reconfirmed; source citations do
  not prove current policy or independent validity.
- No auto-form filling, account login, booking, visa submission, payments,
  forged documents or email sending.

## Safety and privacy
Country-dependent requirements differ by applicant citizenship, residence,
age, school, course, financial situation, permit and policy date. Embassy
jurisdiction depends on current residence, not necessarily nationality.
Examples in a suggested checklist MUST NOT be presented as universal law.
Never give a "ready to submit" certification; students must confirm with
the receiving institution and official government/consular authority.
Use external government sites for changes in law, local missions for
appointment requirements, university sites for degrees and academic criteria.

For example, UK official student visa evidence includes passport and CAS,
and other evidence is conditional. The German Foreign Office directs
students to the relevant mission abroad for precise document lists.
https://www.gov.uk/student-visa/documents-you-must-provide
https://www.auswaertiges-amt.de/en/visa-service/buergerservice/faq/08-studentenvisum-606690

Never put passports, private bank records, credentials or third-party
student identifiers in browser URLs, GitHub issues, log statements or
public research queries. The existing private upload storage is not
end-to-end encrypted; staging should use synthetic files only.
Retention/export/deletion and consent terms are needed before real clients.

## Rollout
This PR is on its own `feat/study-abroad-student-journey` branch based on
`feat/web-browser-agent-research-upgrades`. **Do not merge to main without
explicit user approval.** Includes Alembic migration
`d4ec2f9b7860`; deploy only after verified database and upload backups.
Complete full CI, security dependency updates, live provider tests,
cross-user isolation, migration rollback rehearsal, mobile Safari review
and real source checks before inviting students.

## v2+ roadmap
- Real normalized country/embassy registry and verified governmental sources
- Institution catalog with official program pages, deadlines and evidence timestamps
- Per-document redaction, expiry/translation validators with reviewable output
- Consent flows, source refresh reminders, scholarship and cost calculators
- Case export, progress calendar, notification preferences
- Dedicated Job Visa workflow module with its own statutory logic and tests

## Research consent
An explicit per-request `confirm_share_profile: true` is enforced server-side.
The UI requires opt-in before invoking external Tavily and LLM services.
Study nationality, residence, destination, degree, subject and intake are
included in the public provider query. Document content is NOT shared.
Read the provider privacy terms before using real student information.

## University shortlist
Students can manually save a university, course, public HTTPS program link,
optional deadline and application status (researching/shortlisted/applied/
offer/declined/rejected). These are student-entered data, not verified
university records. All endpoints are protected by study-case ownership;
removing the shortlist row does not change any university application.

Checklist items can store a user-confirmed public HTTPS source link via the
UI. A saved URL is not proof of current legal applicability or official status.
Multiple files under one checklist category are permitted; unlinking a file
retains a different still-linked file before resetting the category.

## Evidence-first accuracy controls (not an accuracy percentage)

- **Official government-domain gate:** curated destination registries are
  used to constrain visa, embassy and pre-departure research. If the chosen
  destination is not covered, the high-stakes research **fails closed**
  instead of inventing requirements. Current registry examples: UK, Germany,
  US, Canada, Australia, Japan, Netherlands, France and New Zealand.
  This is a limited authority-domain index, **not** a complete immigration
  rulebase; regional embassy rules must still be checked manually.
- Hostname checks are exact/suffix-safe; `gov.uk.evil.example` is not official.
  Search candidates are also filtered by the underlying Tavily pipeline.
- Research source metadata distinguishes `official_authority_domain` from
  `unverified_external_source`. A government URL is NOT proof that a
  particular claim, nationality or case condition is legally correct.
- The generated research answer must contain valid provider citations for
  substantive paragraphs and list items. Uncited material is rejected
  rather than silently saved. This is a **citation structure** check, not a
  semantic contradiction/entailment detector.
- Saved sources preserve the date searched and an explicit unknown
  publication-date warning. No automatic claims of fresh/current laws.
- **Case-scoped RAG** asks only the student's attached, processed documents.
  Unlike the general RAG API, an empty case is rejected: it never falls back
  to all the user's files. Recovered citations are checked against exactly
  that case's document IDs. This is useful for transcript/OCR examination,
  but **does not authenticate uploaded documents**.
- Document RAG has separate per-request disclosure consent because excerpts
  may be sent to the configured LLM provider. Public Tavily queries never
  include document excerpts.

Required next steps: evaluate real cases against labeled official documents
with native-speaker review (English, Japanese, Bengali), add authority-aware
entailment checking and source date refresh, verify jurisdiction and
institution recognition, test time limits and costs, and perform privacy/
security threat review before production. No numerical accuracy is claimed.
