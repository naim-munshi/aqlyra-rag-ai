# Study Abroad — conversation-first UI

## User journey

The existing authenticated Study Abroad workspace now opens with **Ask Aqlyra**
instead of a long collection of forms. Users with no plan answer six short
questions in the conversational onboarding flow; the plan is created only
after the last answer. Those who prefer fields can choose "Use guided setup".

For an existing plan, the top conversation allows two explicit modes:
1. **Web research** (opt-in): asks plain-language, source-backed questions
   against the existing \`POST /study-abroad/cases/{id}/research\` service.
   It uses the saved journey profile and optionally one selected program.
   Responses and citations are persisted as scoped research snapshots.
   Research topics can be auto-selected via transparent keyword rules or
   chosen manually. This is one research request per question, **not**
   a general multi-turn LLM with unrestricted memory; the interface must not
   imply automatic university admissions or visa approval.
2. **My documents** (opt-in separately): asks questions about documents
   already linked to the journey via existing case-scoped private RAG. It
   cannot access other journeys. Responses are per-session, and the
   existing document-management panel stays available.

The navigation beneath the chat offers just four choices: My plan,
Universities, Explore topics and Documents. The original feature
components remain mounted and unchanged in API semantics, but hidden
until selected. The old visa/job marketing badges and the redundant
full-width initial warning were removed; safety text stays with the
sensitive action and in the existing verification footer.

## Safety and limits

- NO new database tables, migrations, deletion, account changes, keys,
  deployment environment changes or new third-party data processors.
- Preserve all saved journeys, shortlist, research snapshots, checklists,
  private files and advisor calculations.
- No automatic external research; the existing profile consent is required
  and resets on case switches. Document-excerpt consent remains separate.
- The backend enforces existing query limits (12–160 characters for live
  research, 5–1200 for document RAG) and private-ID/link filters.
- The chat uses existing authenticated BFF endpoints; no raw credentials
  or private documents are sent in web research.
- Official-source checking remains a user responsibility; a cited answer
  is not a guarantee of visa or admissions outcome.

## Rollout

Run existing frontend tests and production-equivalent ARM64 CI on the
frontend production branch. Stage the exact commit, test, then deploy to
production. Verify authenticated account, chat response with citations,
separate document consent, guided setup, navigation, existing journeys,
mobile layout, failure states and no regressions before declaring real-user
acceptance.
