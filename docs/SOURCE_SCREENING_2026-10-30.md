# Automatic ingestion for trusted developer uploads

Updated 2026-10-30 following the decision to trust authorized uploaders and remove manual approval.

## Current flow

Upload by developer -> format/size/parsing checks -> extraction per physical PDF page -> original file and extracted archive -> automatic hashing embeddings -> ChromaDB -> active source.

PDF, Excel/CSV and reference cases all use automatic activation in their upload endpoints. There is no manual approval/rejection action in the dashboard or API. Pending and failed previous uploads can be retried with **Proses ulang**. Legacy rejected material stays inactive.

The internal stored `approved` status now means successful technical activation, not human review or legal verification. Only committed active source IDs are eligible for chat retrieval, telemetry, chunk details and evaluation. The archive briefly remains pending while processing; partial index writes remain ineligible. Failed index writes stay inactive and may be retried. Embedding/model/database technology is unchanged.

## Technical checks and limits

- Existing extension, PDF signature, 20 MB upload size and parser checks apply.
- Encrypted, malformed or textless PDFs fail rather than activate.
- A PDF with a page lacking text is archived with a warning and fails automatic activation, to avoid silently accepting incomplete text. This also flags intentionally blank pages; upload a text-complete copy without blank pages for now. OCR and reliable blank-page/image differentiation are not implemented.
- Parse failures are returned immediately; errors after archiving/indexing leave a failed archive record with a generic error note. No raw internal exception is exposed to the UI.
- There is no automated validation of legal correctness, document authority, tariff validity, complex table structure, or OCR accuracy.
- Cross-page table recovery, parser comparison, trained embedding models, deduplication, background queues and index version switching are future work.

## Storage and audit

- Generated original filenames and SHA-256 content hashes; original bytes remain in ignored `backend/data/uploads/`.
- Extracted text, metadata, uploader account ID and activation mode are stored in `uploads/sources.sqlite`.
- PDF chunks preserve one-based physical page number, page count, document ID and chunk index.
- Original upload identity is retained during retries by another developer; activation identity and timestamp are recorded separately in the existing audit fields.
- Accounts, sessions and chat history are not changed.
- GET `/api/rag/sources`, GET `/api/rag/sources/{id}`, GET `/api/rag/sources/{id}/file`: developer-only archive inspection and attachment download.
- POST `/api/rag/sources/{id}/process`: developer-only automatic retry; CSRF token and exact Origin remain required.
- The old POST review endpoint was removed.
- Evaluation remains a separate manual action when a suitable question/answer dataset exists. Upload form `auto_evaluate` is retained for compatibility but does not trigger evaluation.

## Verification

- Backend suite: 85 tests, including automatic activation, uploader audit, embedding failure/retry, incomplete extraction exclusion and developer/CSRF restrictions.
- TypeScript and isolated production build checked for the updated dashboard.
- The demo PDF remains outside the repository; no document is auto-uploaded for the user.

## User test

Upload the three-page dummy PDF in Dashboard > Sumber data. Successful upload should immediately increase active source counts, and **Status pemrosesan sumber** should show **Aktif**. Open details to inspect physical pages and download the original. Ask a question about the dummy document and verify its source/page citation. No approval button is required. If the source fails, inspect the warnings; retry indexing failures or replace unreadable PDFs.
