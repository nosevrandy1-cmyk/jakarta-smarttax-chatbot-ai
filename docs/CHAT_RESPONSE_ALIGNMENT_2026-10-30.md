# Current-question alignment

Date: 2026-10-30

## Observed issue

The stored dummy-document conversation contained answers to previous questions rather than the latest question. The frontend sent the latest message separately, but the backend assembled multiple consecutive user turns from history and put the newest question inside the reference JSON. This was a suspected contributor, not a proven model-template diagnosis.

## Change

Ollama receives one system message and one user message. The user message contains labeled reference data followed by the latest question in plain text at the very end. Historical user questions are a bounded, clearly labeled completed-history field for resolving follow-up references. Historical assistant claims remain excluded from factual evidence. System guidance explicitly prioritizes the latest question and treats questions printed inside documents as source content, not requests.

No database migration, embedding replacement, model change, generation setting change, or stored chat rewriting was performed. Both streamed and JSON chat responses use the same message builder.

## Validation

87 backend tests passed. New tests verify one current user turn, clear separation of previous questions, exclusion of old assistant claims, and correct latest-question placement across sequential requests. Existing grounding, reference, auth, history and source-ingestion tests remain green. Git diff whitespace validation passed.

A live six-question sequence using local gemma4:12b and the uploaded three-page dummy PDF was run without saving a new account conversation. Results are recorded separately in the local workspace, outside the repository. This small manual comparison is not a general model accuracy benchmark. Real documents, multi-turn pronoun references and larger corpora still need evaluation. Latency and hashing retrieval limitations are not addressed by this change.

## Live sequence result

All six responses addressed their current question in this run: document purpose (page 1), Uji B coefficient and conditions (page 2), Gedung Latihan Biru calculation (page 3), fictional/non-official status, unavailable Uji D information, and correction of the Uji A deduction assumption (page 2). The previous one-question lag did not appear. This is one successful sequence, not a guarantee across all prompts.

Some answers still emitted grouped citation markers such as [1, 2]; the current resolver supports individual markers and therefore does not resolve every grouped marker. Citation formatting remains a separate follow-up; the directly cited core-answer references were present in this run.
