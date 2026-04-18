CSV Import Rules (MVP)

Overview
- Imports are STRICT and will abort on any validation error. The upload will fail with a row-level error report.
- All CSV files must be UTF-8 encoded and use CRLF or LF line endings.
- Required headers must match exactly (case-sensitive) as documented in the `schemas/` JSON Schema files.

Files and headers
- Roster CSV: `Roll Number,Name` (see `schemas/roster.json`).
  - `Roll Number` must be unique. Duplicate roll numbers abort import.
- Timetable CSV: header must include `Day` and exact period columns: `10:00-11:00,11:00-12:00,12:00-13:00,13:00-13:40,13:40-14:40,14:40-15:40,15:40-16:40` (see `schemas/timetable.json`).
  - Use the provided period time format (24-hour) to ensure predictable period mapping.
- Teacher mapping CSV: `Subject,Teacher Name` (see `schemas/teachers.json`).

Validation
- Per-row validation uses the associated JSON Schema.
- Any invalid row, missing required header, duplicate unique key, or malformed field will cause the entire import to fail.
- Error response includes row numbers and human-readable messages.

Timezone & Dates
- The system uses the college local timezone for timetable and event→period mapping. Configure the timezone at import time if the server defaults differ.
- Letters use ISO8601 datetimes (e.g., `2026-05-12T12:00:00`) and must be provided in the college timezone or as offset-aware timestamps.

Post-import
- After a successful import, the system will persist the data and return a summary (rows processed, rows created).
- When importing timetable, the system will validate that every subject referenced either has a teacher mapping or will raise an import-time error.

Operational notes
- Only Maintainer accounts may perform imports.
- Import requests are idempotent at the file level: repeated identical imports will report "no changes" if data is unchanged.
- Rolling back a failed/partial import is not supported for MVP — imports are transactional by design and will not create partial state.

Contact
- For malformed data, contact the College IT maintainer with the CSV and the error report.
