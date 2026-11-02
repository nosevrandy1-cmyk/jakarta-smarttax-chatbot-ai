# Consistent data paths and inline citation styling

Updated 2026-10-30.

## Data paths

Relative CHROMA_PERSIST_DIR and JST_UPLOAD_DIR now resolve against the backend directory, rather than the shell working directory. Absolute overrides continue to work. Defaults remain backend/smarttax_vectordb and backend/data/uploads. No .env file was overwritten and no vector database technology was changed.

Local cleanup verified the intended backend/smarttax_vectordb location, backed up 44 inactive legacy records outside the repository, and deleted only those records. All nine active chunks from the two uploaded PDF documents remained intact. Original files, source archive records, accounts and chat history were not removed. This is a local maintenance action, not startup behavior and not an automatically repeated migration.

## Citations

Grouped markers such as [1, 2] now resolve all allowed source numbers while retaining their original grouping. Unknown numbers are filtered; repeated sources appear once in the reference data. The chat renders individual and comma-grouped numeric markers in blue using the theme accent. Groups are not split into separate markers. Existing expandable source cards remain available. Inline code is not recolored as a citation.

Existing stored responses are recolored on render, but their saved reference metadata is not reconstructed retroactively. Newly generated answers use the updated resolver. Numeric brackets are visually recognized by syntax; blue alone does not prove source correctness.

## Verification

91 backend tests passed, including working-directory-independent path resolution, preserved absolute overrides, grouped references and unknown-ID filtering. TypeScript with noUnusedLocals and an isolated Next.js production build passed. The live chatbot DOM confirmed blue citation styling (dark-theme rgb 147,197,253). No new account conversation was created during verification.
