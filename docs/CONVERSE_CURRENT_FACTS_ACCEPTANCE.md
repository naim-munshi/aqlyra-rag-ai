# Aqlyra Converse: current public facts and officeholder safeguards

This work closes a screenshot regression from the live `aqlyra-ai.vercel.app`
Converse UI. The prompt `Who's the prime minister?` did not name a
country, and an unsourced model gave a stale, confident answer about
Bangladesh. As of 31 October 2026, the official Cabinet Division lists
Tarique Rahman as Bangladesh's prime minister, appointed 17 February 2026.
Reference: https://cabinet.gov.bd/ (the government source, not a model fact).

## Corrected decision flow

1. If the user asks who currently holds a prime minister/president office
   without any jurisdiction (EN/BN/JA), ask which country. **No AI provider,
   browsing provider, memory or paid model call.**
2. When the country is specified and Web Auto is enabled with a working
   Tavily key, route to verified public web research even without the words
   `latest`, `current` or `today`; add an as-of date and official
   government source preference. The public query contains the **current
   question only**, never private chat history, file content or memory.
3. If the assistant just asked which country and the next user message is
   only a country (for example `Bangladesh`), reconstruct the standalone
   public officeholder lookup using only the preceding generic question and
   the selected jurisdiction. The prior assistant response must match the
   local clarification exactly. No unrelated private context is shared.
4. Explicit Web On/Deep still use the verified source service; Web Off and
   unavailable/misconfigured live provider must not fall back to a guessed
   current officeholder. Return an uncertainty message instead.
5. Streaming and synchronous Converse both call the shared guard.
   Uploaded file/Knowledge paths are unchanged and never sent to public
   search automatically.
6. An answer about a changing incumbent should cite actual extracted sources;
   if recent official evidence cannot support it, do not fabricate a name.

## Acceptance (not equivalent to green CI)

- Repeat `Who's the prime minister?` in a brand-new guest/authenticated
  Converse chat: it should ask which country. No hardcoded Bangladesh.
- Ask `Who is the prime minister of Bangladesh?` with **Auto**: requires
  actual Tavily, up-to-date official sources and correct adjacent citations.
- With Tavily disabled or Web Off: return a clear unable-to-verify message.
- Test Bangla `বাংলাদেশের প্রধানমন্ত্রী কে?` and Japanese
  `日本の首相は誰？`.
- Check network telemetry for one search decision per turn; do not log or
  forward private uploaded documents, history or memory to Tavily.
- Verify normal general explanations and historical questions still work.
- Repeat on mobile Safari, the exact production branch/commit, a second
  authenticated account, and after restart.

**Production gate:** This source-only patch does not create, fund or configure
a Tavily account; no verified production live search is claimed. The existing
main-merge approval, database/off-host-backup, owner isolation and exact-head
CI release rules remain in place.
