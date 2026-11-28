# Study Abroad — included product feature

## Scope

Study Abroad is included in Aqlyra's unified release candidate. It provides a private student-planning workspace for university discovery, admissions, scholarship research, student-visa/embassy research, document readiness, and evidence-linked notes.

It is **not** an immigration law service, licensed adviser, application representative, embassy booking agent, or guarantee of university admission, scholarship, legal eligibility, or visa approval.

## Application integration

- Authenticated frontend: `/study-abroad`.
- Frontend API proxy: `/api/study-abroad/*`; only bounded path segments are forwarded to the configured backend.
- Backend API prefix: `/api/v1/study-abroad`.
- Backend routers include student cases, case documents, checklist items, research, university shortlist, Study Fit, Evidence Brief, and Program Research.
- Database migration: `d4ec2f9b7860`.
- Source files include `backend/app/api/study_abroad.py`, `backend/app/api/study_fit.py`, `backend/app/api/study_evidence_brief.py`, `backend/app/api/study_program_research.py`, and `frontend/src/components/study-abroad/study-abroad-workspace.tsx`.

## Privacy and data handling

- Every case is owned by the authenticated user. Case, linked-document, research, and shortlist endpoints must enforce that owner relationship server-side.
- A document can be linked only when it is owned by the authenticated user and has reached the expected processed/ready state.
- Removing a case or unlinking a document must not delete the user's original document unless the user separately requests deletion through the document lifecycle.
- Research requires explicit profile-sharing consent. Uploaded document content is not included in public research queries.
- Case-document RAG requires separate per-request consent before retrieved excerpts are sent to the configured AI provider. Retrieval must be restricted to documents linked to that case and must not fall back to all user documents.
- Do not store passport numbers, birth dates, account credentials, or third-party student identifiers in URLs, public issues, or logs.

## Evidence and accuracy constraints

- Research reports preserve the search date and source metadata. A source being on a government domain does not prove that its content applies to a particular applicant.
- High-stakes topics should fail closed when the configured official-source coverage is missing or source evidence is insufficient.
- Suggested checklists are planning prompts, not universal legal requirements.
- Users must confirm deadlines, document lists, jurisdiction, and current rules with the relevant university and official government/consular authority.
- The service must not claim that it has submitted an application, booked an appointment, or verified document authenticity.

## Upload constraints

The current authenticated Vercel-to-backend private upload proxy is capped at **3 MiB per file** to stay below the function request-size limit. UI error messages must not claim a 25 MiB limit for this upload path. Larger files require a separately accepted direct/private upload flow; do not imply that it is enabled by this route.

## Required acceptance before production use

1. Run the `d4ec2f9b7860` migration on a restored disposable staging database; verify migration head and table readiness.
2. Create two independent test accounts. Confirm user A cannot list, read, modify, link, unlink, or query user B's Study Abroad cases, research, university records, or documents.
3. Exercise case create/update/delete, checklist edits, multiple document links, report retrieval, university shortlist CRUD, and Study Fit / Evidence Brief / Program Research routes.
4. Verify explicit profile-sharing and document-sharing consent boundaries.
5. Test official-source filtering, source freshness labels, citation coverage, unsupported-claim refusal, and no-admission/no-visa-guarantee language.
6. Verify the `/study-abroad` page, sidebar navigation, authenticated BFF proxy, upload flow, and backend API against the same candidate commit.
7. Test Japanese, Bangla, and English UI/content rendering and mobile layout.

## Release status

Source integration in `release/study-abroad-included-20261129` is not proof of production deployment or acceptance. The live Render commit, production migration head, RLS/tenant controls, and real two-account staging E2E must be verified independently. Do not enable or announce this workflow as production-accepted until the gates above pass.