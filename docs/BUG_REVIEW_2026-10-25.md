# Aqlyra targeted bug and security review — 2026-10-25

Scope: main commit `6bd16d5`, review of login, chat, workspace navigation,
and the new proposed web research flow. This is a targeted code review, not
a comprehensive penetration test or a live production audit.

## Observed issues and tracked remediations

- Login's **Forgot password?** action was inert. **PR #11** adds proper OTP
  password recovery. Do not declare it deployed until manual verification.
- Authentication proxy forwarded a browser-provided client-IP header, enabling
  spoofing if Redis IP limits were enabled. **PR #10** removes untrusted header
  forwarding by default. Merge after review and re-test real ingress.
- Sidebar **Upgrade**, **Upgrade plan**, and **Help** buttons have placeholder
  click behavior, rather than a functioning billing or documentation flow.
  Do not advertise paid plans before implementing entitlement/billing.
- Docker Desktop on the operator Mac logged EXT4 write I/O errors and an
  aborted journal. This is a local infrastructure incident, not an Aqlyra
  Python defect. Recovery should preserve Docker volumes and verified backups.
  Native PostgreSQL on a separate port is a temporary local workaround.
- Before this feature, no real web browsing provider was integrated into the
  authenticated product. This branch adds a bounded search/extract/synthesis
  workflow; it is disabled by default until owner-supplied API credentials.

## Remaining validation

- Automated regression suite on the feature PR branch.
- Live external provider smoke test with an actual Tavily key and
  configured Groq/OpenAI LLM (never send keys in GitHub issues).
- Verify source quality, citation support and multi-language answers.
- Production ingress rate limiting and cost quota settings.
- Password reset PR #11 must merge first; this web PR is stacked on PR #11.
