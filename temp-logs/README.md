# AVAN diagnostic exports

Run `scripts/export-avan-diagnostics.ps1` on the Docker host. Add `-Push` to
commit the new JSON export and push the current branch to origin. Existing
commits on that branch will also be pushed by normal Git behavior.

Only the structured diagnostic stream is exported (last 2000 events). It includes
request correlation, route templates, timings, status codes, phase and exception
types/stack locations. It excludes exception messages, request/response bodies,
file names/content, SQL, credentials, conversation text and audio.

The running service rotates five files of at most about 2 MB each under its
existing persistent AVAN_STATE_DIR. Older events are discarded. Export before
rotation when investigating a problem. A request ID from the UI helps correlate
events; it is not an authorization token. GodAdmin can also download runtime
diagnostics from the support page. Other users receive only their authorized
audit metadata.

Git retains committed exports in history even after file deletion. Do not add raw
Docker logs, environment files or arbitrary debug dumps to this directory.
These diagnostics cover instrumented application requests and native uploads;
container startup, host crashes and external services require their own diagnosis.
