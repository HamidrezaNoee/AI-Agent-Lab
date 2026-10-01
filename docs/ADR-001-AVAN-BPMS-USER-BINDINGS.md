# ADR-001 — AVAN-native users with per-BPMS identity bindings

Status: Accepted  
Date: 2026-10-01

## Decision

AVAN user accounts, authentication, AVAN roles and AVAN permissions are independent
from every connected BPMS. A BPMS account is an external execution/data identity,
not the AVAN login identity and not the source of AVAN roles.

One AVAN user may have zero, one or many BPMS bindings, at most one active binding
per BPMS source.

Example:

- AVAN user: `amin.t`
- ProcessMaker A -> `ali.j`
- ProcessMaker B -> `amin.t`
- Camunda C -> `user_417`

The usernames do not need to match.

## Domain model

### AvanUser

Stable AVAN identity. The authoritative key is the verified OIDC/Keycloak subject.
AVAN username, role, MFA, tenant membership and application permissions remain
AVAN-managed.

### BpmsSource

One configured BPMS connection. Each source has a stable AVAN source ID, engine
type, name, enabled state and read-only integration configuration.

### BpmsDirectoryUser

Read-only directory projection from one BPMS source. Minimal metadata only:

- source_id
- external_user_id
- username
- display_name
- email when available
- active/status
- last_seen_at
- directory snapshot/version

Never import password hashes, authentication secrets or privileged source fields.

### UserBpmsBinding

Explicit mapping:

- tenant_id
- avan_subject
- source_id
- external_user_id
- binding_status: active / inactive / stale
- match_method: manual / username_suggestion / email_suggestion
- approved_by
- approved_at
- last_verified_at

Constraints:

- unique (tenant_id, avan_subject, source_id)
- unique (tenant_id, source_id, external_user_id) by default
- source and target external user must exist and be active before activation

## Matching and admin workflow

In "سازمان و دسترسی":

1. Admin selects an AVAN user.
2. Admin selects one configured BPMS.
3. AVAN synchronizes/reads that BPMS directory.
4. AVAN suggests likely matches, in this order:
   - exact normalized username
   - exact verified email
   - display-name similarity only as a low-confidence hint
5. A suggestion never grants access by itself.
6. Admin may accept the suggestion or search/select any other active BPMS user.
7. AVAN saves the explicit binding and audits the decision.

Example: AVAN may suggest ProcessMaker user `amin.t`, but the Admin may explicitly
bind AVAN `amin.t` to ProcessMaker `ali.j`.

## Authorization rule

A BPMS binding scopes data and BPMS-derived capabilities. It does not assign AVAN
roles and does not replace AVAN authorization.

Effective access is the intersection of:

- valid AVAN session + tenant membership
- AVAN role/permission
- licensed/enabled AVAN module
- enabled BPMS source
- active UserBpmsBinding for that source
- current external BPMS-user status/capability/scope

Client-side menu visibility is only presentation. Every API must enforce the same
rule server-side.

If a user is bound only to BPMS A, menus/data belonging exclusively to BPMS B must
not be available. If the user has bindings to A and B, the UI may expose both
sources and source-aware modules.

## Multi-BPMS behavior

AVAN must not assume ProcessMaker is the only directory. Each BPMS adapter exposes
a common directory contract to AVAN, while engine-specific code remains behind the
adapter.

Required conceptual operations:

- list/sync users for source
- resolve external user by stable external ID
- verify user status
- provide source-specific data scope/capabilities for that external user

ProcessMaker is one implementation of this contract, not the identity authority.

## Sync behavior

Directory synchronization is read-only and may be manual plus scheduled.

- Sync never creates or mutates AVAN users.
- Sync never automatically binds identities.
- A missing/inactive external account marks its binding stale/inactive.
- Reappearing users are re-verified by stable external ID, not by username alone.
- Username changes in a BPMS do not change the AVAN username.

## Security

- No BPMS password is stored for end users.
- Integration credentials remain server-side.
- Binding changes require an authorized AVAN Admin/GodAdmin and CSRF-protected API.
- Create/change/remove/approve operations are audited.
- External username/email matches are suggestions only.
- Never trust a browser-supplied external user ID without verifying it belongs to
  the selected source and current tenant.

## Migration impact

Current code contains ProcessMaker-centric assumptions:

- `identity_operator.py` creates an AVAN identity from a verified PM user.
- `processmaker_directory.py` is a PM-specific directory reader.
- pending identity wording and some access paths assume one PM mapping.

These must be refactored toward AVAN-native account creation plus per-source
`UserBpmsBinding`. Existing ProcessMaker mapping data should be migrated as a
binding to the corresponding ProcessMaker source, not treated as the AVAN identity.

## UI requirement

"سازمان و دسترسی" must show, per AVAN user:

- AVAN account identity and AVAN role/permissions
- a separate "اتصال به BPMSها" section
- BPMS selector
- sync/refresh directory action
- suggested match with reason
- searchable external-user selector
- explicit bind/change/remove actions
- status for every configured BPMS

The AVAN account form and BPMS-binding form must remain visually and logically
separate.
