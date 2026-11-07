# Aqlyra Microsoft Office document reading and preview

Code review baseline: `feat/real-web-research-agent` at `e7ea97c`.
The project already supported Office upload, parser, database units, embeddings,
and RAG citations for modern Word, Excel, and PowerPoint files.

## Supported functionality

| Format | Upload | Extract | Private preview | Original download |
| --- | --- | --- | --- | --- |
| Word `.docx` | Yes | Paragraphs, tables, headers/footers | Yes | Yes |
| Excel `.xlsx` | Yes | Multi-sheet cells, cached values, fallback unevaluated formulas, coordinates | Yes | Yes |
| PowerPoint `.pptx` | Yes | Text, tables, speaker notes | Yes | Yes |
| PDF | Yes | Existing PDF parser | Existing PDF viewer | Yes |
| CSV, TXT, Markdown, images | Yes | Existing parsers | Existing behavior | Yes |

The Office viewer renders **extracted plain text**, not pixel-perfect
Microsoft Office rendering. It never executes formulas, macros, linked
resources, or embedded code. The original remains downloadable and can be
edited using Microsoft Office/LibreOffice on the user's computer.

Older binary `.doc`, `.xls`, `.ppt`, macro-enabled `.docm`, `.xlsm`,
`.pptm`, OneNote, Visio and encrypted/password-protected documents are not
supported in this release. Convert them to `.docx`, `.xlsx`, or `.pptx`
using trusted Office software before uploading. Do not rename the extension;
that does not convert its underlying format.

## Security and isolation

The Office preview fetches existing document units through a new Next.js
`GET /api/documents/{id}/units?offset=...` proxy. The session JWT stays
server-side; backend authorizes document ownership, supports pagination
and returns sanitized JSON rather than raw executable Office content.
No third-party online Office viewer sees private uploads. Preview content
is plain React text and does not interpolate HTML.

Spreadsheet parser places cell coordinates next to each extracted cell
(`A2: Value | B2: 1200`) so RAG can cite the correct sheet/row/cell.
Only saved cached formula values or the formula expression itself are
available; **formulas are not evaluated** and charts/images are not visually
rendered. Data extraction has row, column, cell and character limits;
the UI flags truncation rather than silently asserting full coverage.

The dedicated viewer supports up to 30 sections/sheets/slides per page,
mobile section navigation, a read-only 20k character preview per unit, and
original-file download. Existing database and file storage contracts stay
unchanged: **no migrations, reindex or data resets** are required to activate
the new viewer. Previously processed files retain earlier extraction units
unless explicitly re-uploaded/reindexed.

## Verification

Backend regression tests construct real `.docx`, `.xlsx`, and `.pptx`
files, run the parsers, upload and process each file, and verify authenticated
access to extracted units. Frontend lint/typecheck/build checks the preview.
Not a replacement for full Word/Excel/PowerPoint editing.
