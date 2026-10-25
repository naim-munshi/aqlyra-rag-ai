# Aqlyra Chat + Tools Menu

This UI change keeps the original Converse/Knowledge chat composer, uploads,
and RAG conversation behavior. Only the entry points for tools move.

## User experience

The previous paperclip control immediately opened the local file picker.
It is replaced by the **+** button next to the text composer in both empty
and ongoing conversations. Select the following actions in order:

1. **Upload file** — invokes the exact existing hidden input, upload,
   duplicate detection, backend processing and attachment preview. It does
   not send the file to a new third-party provider.
2. **Web Research** — navigates to the existing authenticated `/web`
   research workspace for real Tavily search and citation-backed answers.
3. **Browser Agent** — navigates to `/agent/browser` to review the task,
   URL restrictions and approval plan before any permitted navigation.
4. **Knowledge chat / Switch to Converse** — switches the current chat mode
   using the existing per-mode conversation state.
5. **My documents** — opens the existing documents drawer.

Web Research and Browser Agent are **removed from the main sidebar**. The
Documents and RAG Chat shortcuts remain.

This does not automatically combine private file attachments with third-party
web research; they remain intentionally separate workflows. Clicking an agent
does not activate autonomous website actions inside the current chat. Neither
agent is enabled in production merely by exposing its menu entry.

## Accessibility and interaction

The menu is a single-column popover above the composer, sized for mobile.
The trigger reports `aria-haspopup=menu` and `aria-expanded`; the menu has
appropriate roles. Escape closes and restores focus, outside click/focus
dismisses, ArrowUp/ArrowDown and Home/End navigate options.

The upload picker opens synchronously from its menu click to retain the
Safari user activation requirement. While a message is generating or a file
is processing, the menu trigger is temporarily disabled.

## Manual acceptance after checking out branch

- Verify the + menu in a blank chat and with existing conversation history.
- Choose Upload file and confirm native Safari file picker; upload/process a
  small DOCX/PDF and ask a question as before.
- Confirm Web Research and Browser Agent routes require authentication.
- Approve an agent only on an explicitly configured development environment.
- Switch Converse to Knowledge and back without losing stored conversations.
- Open Documents from + and verify the drawer closes normally.
- Confirm Web Research and Browser Agent are absent from sidebar.
- Test a narrow mobile viewport, Escape, keyboard arrow navigation and
  outside click dismissal.

Run frontend checks with locked dependencies. Review the pending
dependency security audit and older stacked PRs before production merge.
No migrations or document-data modifications are needed.
