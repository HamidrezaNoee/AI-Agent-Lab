# Smart Secretary Conversation Resolution Layer

## Purpose

AVAN must understand multi-turn Persian confirmations without weakening the evidence boundary around LLM extraction.

A reply such as:

- `بله`
- `بله همان است`
- `مورد تاییده`
- `نه، mgr.sales`
- `administrator`
- `مسئول اقدام ۲ mgr.sales باشد`

must not force the model to re-invent the referenced value. If AVAN has already proposed one concrete candidate, the confirmation is resolved by deterministic application code.

## Pipeline

A Smart Secretary turn is processed in this order:

1. **Normalization**
   - Persian/Arabic character normalization.
   - Persian/Arabic digit normalization.
   - Preserve dots inside usernames such as `mgr.sales`.

2. **Pending Confirmation Resolver**
   - Uses a versioned `pending_confirmation` stored with the draft.
   - Resolves affirmative, negative, repeated-identity and correction replies without an LLM call.
   - Revalidates the candidate against the current active BPMS directory.
   - Applies only to an explicit PMX field path.

3. **Direct Identity Resolver**
   - Handles explicit identities when exactly one target UID field is unambiguous.
   - Multiple unresolved action owners require an explicit row/action reference.
   - Questions and negations never become edits.

4. **Deterministic Draft Q&A**
   - Read-only questions about already collected draft data are answered without a model where possible.

5. **Structured LLM Extraction**
   - Used for genuinely new facts.
   - Every assignment must still have evidence copied from the new user message.
   - The model cannot use historical text as assignment evidence.

6. **Validation and Commit**
   - PMX schema validation.
   - Active-user validation.
   - Revision/native-state checks.
   - Cancellation check before commit.
   - Process advancement is separate from field confirmation.

## Pending confirmation contract

A pending identity proposal contains:

- version
- kind
- field path
- candidate UID (server-only)
- display value
- original missing-field question
- expected current field value
- created timestamp
- expiry timestamp
- source

The client receives only review-safe metadata. Candidate UIDs remain server-side.

## Safety invariants

- Never select the first person from multiple candidates.
- Never infer an identity from a job title without a unique validated mapping.
- Never confirm an inactive/deleted BPMS user.
- Never overwrite a field changed after the proposal was created.
- Pending confirmations expire.
- Manual form edits and file-driven edits invalidate conversational proposals.
- A field confirmation returns intent `resolved`, not `update`; therefore it cannot implicitly advance a ProcessMaker case.
- Old drafts can reconstruct a pending proposal only from the last assistant message when that message names exactly one active candidate and one unambiguous missing UID path.
- LLM evidence remains restricted to the new user message; historical context is not silently accepted as assignment evidence.

## Diagnostics

Structured model validation failures expose stable, non-sensitive codes:

- `AI_EVIDENCE_MISMATCH`
- `AI_EXPLICIT_SECTION_OMITTED`
- `AI_INCOMPLETE_OUTPUT`
- `AI_STRUCTURED_OUTPUT_REJECTED`

Deterministic confirmations are audited as `SECRETARY_CONFIRMATION_RESOLVED` without storing conversation text.
