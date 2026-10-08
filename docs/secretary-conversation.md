# AVAN Conversational Secretary Contract

## Goal

The AVAN secretary is the conversational front end of the installed ProcessMaker
meeting pack. It does not invent a parallel workflow engine. Native ProcessMaker
assignments, triggers and routing remain authoritative.

## Meeting start

1. An AVAN user opens **شروع جلسه با دبیر هوشمند** for a configured
   `meeting_v2` pack.
2. AVAN creates only an Agent-side draft. No ProcessMaker case exists yet.
3. The user may provide:
   - Persian text;
   - microphone audio, transcribed to Persian text;
   - an uploaded text-bearing PDF, DOCX, TXT, MD, CSV or JSON document.
4. The model receives only the PMX fields allowed for the invitation stage plus
   the active BPMS directory. It may extract explicit facts, but must leave
   unknown facts blank.
5. AVAN deterministically calculates missing required fields and asks only for
   those fields.
6. `MTG_MeetingNo` is not requested from the user for a new case. It is owned
   by the native ProcessMaker BEFORE trigger.
7. When the invitation is complete, the assistant asks for explicit creation
   confirmation. A direct instruction such as **بله، ایجاد و ارسال کن** creates
   the native case.
8. AVAN executes the reviewed PMX BEFORE trigger, reads the native generated
   meeting number/form date, writes the reviewed invitation variables, executes
   reviewed AFTER triggers and routes the case.

## Chair inbox and approval

The PMX assignment for the invitation-approval task remains authoritative. The
chair is resolved by ProcessMaker from `MTG_ChairUserUID`.

If that ProcessMaker identity is bound to an AVAN account:

- the task appears in **کارتابل من / تأییدهای من**;
- AVAN shows a deterministic textual summary of the invitation;
- the same summary can be read through configured TTS;
- the chair can answer by text or microphone audio;
- explicit phrases such as **دعوت‌نامه را تأیید می‌کنم** are mapped
  deterministically to the native `Approved` decision;
- a revision request needs its correction/comment before routing;
- only an explicit human decision may auto-route an approval stage.

Users without personal ProcessMaker write authorization may still load and hear
their assigned task. The write/route controls stay unavailable until their
personal ProcessMaker authorization is connected.

## Files

Raw conversational uploads are never executed and are not persisted in Agent
storage. AVAN extracts bounded text and stores only attachment metadata plus the
workflow fields derived from reviewed text. DOCX parsing reads
`word/document.xml` only; macros, relationships and embedded objects are
ignored.

Current conversational file limits:

- maximum raw size: 8 MiB;
- maximum extracted text: 18,000 characters;
- supported: text PDF, DOCX, TXT, MD, CSV, JSON.

Native ProcessMaker case documents remain a separate evidence path and retain
native assignment checks.

## Interaction guarantees

- Enter sends; Shift+Enter creates a new line.
- Audio may be converted to text before sending.
- Optional voice mode sends the transcript automatically and attempts to read
  the assistant response.
- Files support chooser and drag/drop.
- The generated PMX form remains available under a collapsed
  **مشاهده / اصلاح فرم استخراج‌شده** section.
- Manual form editing does not bypass revision checks.
- Every remote ProcessMaker write revalidates current assignment/revision.
- Timeouts never cause blind duplicate case creation or routing.

## Next stages

The same conversation shell is used for:

- minutes collection;
- minutes approval;
- action execution report;
- secretary action review;
- meeting monitoring and closure.

Each stage keeps its own typed PMX field allow-list and explicit human decision
boundary.
