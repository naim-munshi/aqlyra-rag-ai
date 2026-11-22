# Aqlyra reproducible demo kit

This directory contains **synthetic** example content only. It is deliberately safe to upload into a test account because it has no private customer data.

1. Sign into the real application at https://aqlyra-ai.vercel.app with a test account.
2. In Knowledge mode upload [fixtures/synthetic_support_policy.txt](fixtures/synthetic_support_policy.txt). A PDF conversion using a trusted local tool is optional; do not use sensitive documents.
3. Ask: **"What are support hours? Cite the file."** Expected: Monday–Friday, 09:00–17:00 JST, with a matching document citation.
4. Ask: **"What are emergency channels?"** Expected: the illustrative ticket queue, cited accurately.
5. Ask: **"What is the payment amount or refund deadline?"** Expected: the document does not supply a payment amount, and a refund deadline is **not defined** (avoid inventing numbers).
6. Repeat from a separate account without sharing files; user B must not access user A's document. A UI hiding the file is *not* sufficient—verify the backend rejects direct access.
7. Use the explicitly scripted https://aqlyra-ai.vercel.app/demo page to show sample UI and architecture without a login or model/provider charges.

**No actual voice/video recording, private-session test data or externally verified two-user test output is included here.** See [Product demo and acceptance](../docs/PRODUCT_DEMO_AND_ACCEPTANCE.md) for evidence criteria.
