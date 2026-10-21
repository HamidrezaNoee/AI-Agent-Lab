# Validation — 2026-10-18

Base: main `293bcdb20c8be673d407baaf267ee69bdd92ad15`.
Delivery branch: `fix/avan-pmx-voice-diagnostics-20261017`.

## Results and limits

- Focused Python suite: **138 passed**. Covers PMX adapter/aliases, seven-stage
  REST ordering, native attachments, diagnostics privacy/scope and lexical retrieval.
- Chromium secretary desk fixture: **passed**, including stage navigation, form/chat
  updates, responsive layout, settings and support logs. The toast clock fixture now
  pauses virtual time before checking the exact timeout, avoiding wall-clock races.
- Chromium voice fixture: **passed** using actual WebAudio/MediaRecorder with a
  synthetic audio stream and mocked STT/chat/TTS callbacks. Verified reactive
  amplitude, interruption, mobile width, abort and stopped microphone tracks.
- Desktop/mobile orb and support-page screenshots inspected locally.
- JavaScript syntax, Python compilation, diff whitespace and 10 module contracts pass.
- Full current Python run: **681 passed, 24 failed, 8 setup errors, 55 subtests passed**.
  Full CI is **not green**; this is a draft PR and not a production release claim.

For comparison, a separate checkout of unmodified main with the same dependencies
and restored static assets produced **608 passed, 42 failed, 52 setup errors,
55 subtests passed**. The final failure IDs also fail on main or are assertions
previously blocked by missing fixtures. In particular, adding only the missing
`pack` import to the baseline all-stage coverage test reproduces both exposed
minutes-approval/action-review assertions. No production logic was weakened to
satisfy those expectations.

Remaining failures include stale requiredness/identity expectations, missing test
fixtures, old REST stubs without `variables`, and retry-budget expectations. Some
may describe real pre-existing behavior requiring a separate decision; they have
not been relabeled as passed or skipped. Relevant repaired fixtures were updated
for strict requiredness parameters, complete draft payloads and current PMX hashes.

No live PM server/PHP trigger, SQL Server, Keycloak, paid transcription/TTS or Docker
host was accessed. Payment's final-form document binding still requires Designer
correction and a live acceptance case. Voice is turn-based, not full-duplex Realtime.
PowerShell export was reviewed but not executed on a Windows Docker host.

## Focused reproduction

```bash
python -m pytest commercial/tests/test_avan_diagnostics_retrieval.py commercial/tests/test_secretary_native_files.py commercial/tests/test_user_experience.py commercial/tests/test_agent_completion.py commercial/tests/test_secretary_inbox.py commercial/tests/test_meeting_pair_execution.py commercial/tests/test_secretary_live_requiredness.py -q
node commercial/tests/live_voice_browser.cjs
node commercial/tests/secretary_desk_browser.cjs
python scripts/ai-context.py check
```

Browser tests use Playwright; optionally set `CHROMIUM_PATH` for an installed
Chromium and `AVAN_SCREENSHOT_DIR` for screenshots. Test HTTP/service data is mocked.

## Remaining full-suite failures

```text
FAILED commercial/tests/test_secretary_ai_context.py::test_omitted_explicit_sections_retry_then_report_instead_of_silent_success
FAILED commercial/tests/test_secretary_all_stage_full_turn_coverage.py::test_every_non_minutes_dense_stage_is_detected[action_review]
FAILED commercial/tests/test_secretary_all_stage_full_turn_coverage.py::test_dense_stage_routes_directly_to_full_extraction[minutes_approval]
FAILED commercial/tests/test_secretary_commands.py::test_progress_question_reports_human_next_gap_without_llm
FAILED commercial/tests/test_secretary_conversation_regressions.py::test_sparse_grid_questions_keep_native_row_ids
FAILED commercial/tests/test_secretary_conversation_regressions.py::test_concurrent_direct_submit_is_rejected_before_second_write
FAILED commercial/tests/test_secretary_conversation_regressions.py::test_failed_direct_submit_keeps_revision_for_explicit_retry
FAILED commercial/tests/test_secretary_resolution.py::test_pending_confirmation_is_built_from_unique_explicit_candidate
FAILED commercial/tests/test_secretary_resolution.py::test_short_affirmations_apply_pending_value_without_model[\u0628\u0644\u0647 administrator]
FAILED commercial/tests/test_secretary_resolution.py::test_explicit_correction_overrides_pending_candidate_without_model
FAILED commercial/tests/test_secretary_resolution.py::test_admin_alias_can_resolve_only_known_unique_administrator
FAILED commercial/tests/test_secretary_resolution.py::test_multiple_missing_owners_require_explicit_row_reference
FAILED commercial/tests/test_secretary_resolution.py::test_model_generated_confirmation_becomes_structured_pending_state
FAILED commercial/tests/test_secretary_resolution.py::test_legacy_history_reconstructs_pending_confirmation_without_model
FAILED commercial/tests/test_secretary_resolution.py::test_direct_identity_answer_bypasses_model_without_pending[administrator-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED commercial/tests/test_secretary_resolution.py::test_direct_identity_answer_bypasses_model_without_pending[\u0627\u062f\u0645\u06cc\u0646-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED commercial/tests/test_secretary_resolution.py::test_direct_identity_answer_bypasses_model_without_pending[\u0645\u0633\u0626\u0648\u0644 \u0627\u0642\u062f\u0627\u0645 \u06f1 mgr.sales \u0628\u0627\u0634\u062f-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb]
FAILED commercial/tests/test_secretary_resolution.py::test_identity_question_never_mutates_directly
FAILED commercial/tests/test_secretary_resolution.py::test_dotted_username_with_spaces_resolves_against_latest_assistant_action
FAILED commercial/tests/test_secretary_resolution.py::test_finance_manager_role_alias_resolves_current_action_without_model
FAILED commercial/tests/test_secretary_workflow.py::test_revision_and_source_isolation
FAILED commercial/tests/test_secretary_workflow.py::test_send_waits_for_native_chair_and_rejects_duplicate
FAILED commercial/tests/test_secretary_workflow.py::test_timeout_is_never_blindly_replayed
FAILED commercial/tests/test_secretary_workflow.py::test_monitoring_exactly_one_day_before_planned_end
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_dense_invitation_goes_to_full_extraction_not_temporal
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_dense_invitation_is_detected_as_compound
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_coverage_detects_every_major_omission
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_complete_dense_invitation_satisfies_coverage
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_model_partial_first_answer_is_retried_until_full_coverage
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_coverage_requires_member_required_position_presenter_and_minutes
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_dense_message_misclassified_as_question_is_retried
ERROR commercial/tests/test_secretary_full_turn_coverage.py::test_prior_action_inside_agenda_is_part_of_coverage
```
