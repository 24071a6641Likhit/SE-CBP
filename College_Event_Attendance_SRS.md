# College Event Attendance Coordination System — Software Requirements Specification (SRS)

Version: 1.0

Date: 2026-04-10

Prepared by: Software Requirements Architect

---

## Table of Contents

- 1. Introduction
  - 1.1 Purpose
  - 1.2 Scope
  - 1.3 Audience
  - 1.4 Definitions, Acronyms & Abbreviations
  - 1.5 References
- 2. Overall Description
  - 2.1 System Context
  - 2.2 Actors and Stakeholders
  - 2.3 Product Perspective
  - 2.4 Operating Environment
  - 2.5 Design Constraints
  - 2.6 Assumptions and Dependencies
- 3. External Interfaces
  - 3.1 User Interfaces
  - 3.2 Software Interfaces
  - 3.3 Communications Interfaces
- 4. Functional Requirements
- 5. Non-Functional Requirements
- 6. System Models (Use Cases & Flows)
- 7. Data Model
- 8. API & Real-time Events (MVP Sketch)
- 9. Security, Privacy & Audit
- 10. Edge Cases & Failure Handling
- 11. Testing & Acceptance Criteria
- 12. Deployment, Maintenance & Operational Notes
- 13. Risks and Mitigations
- 14. Open Issues
- 15. Appendix
  - A. Sample CSVs
  - B. Sample Letter Template
  - C. Sample Event→Period Mapping

---

## 1. Introduction

### 1.1 Purpose

This document is a Software Requirements Specification (SRS) for the "College Event Attendance Coordination System". It specifies clear, testable, and implementation-ready functional and non-functional requirements for an MVP that enables students to submit event letters, coordinators to approve/reject them, and teachers to receive prefilled attendance for affected class periods.

The SRS is intended to be used by product owners, developers, QA, and maintainers to build and verify the system.

### 1.2 Scope

The system (MVP) provides:

- Three responsive web front-ends: Student, Coordinator, Teacher.
- Backend services (REST API, datastore) and a real-time update mechanism (WebSocket/SSE with polling fallback).
- CSV import utilities for roster, timetable, and teacher mappings.
- Template-driven structured letters (pre-filled fields + editable free text).
- Rules that map event time intervals to pre-defined college periods; any overlap marks a period as affected.
- Automatic attendance prefill for approved events with teacher-editable marks and full audit trail.

Out of scope for MVP:

- Native mobile apps
- Full SIS integrations beyond CSV import
- Automated external notifications (SMS) — optional for later
- Advanced RBAC beyond Student/Coordinator/Teacher roles
- Financial/accounting features

### 1.3 Audience

This SRS is written for:

- Developers and architects implementing the system.
- QA engineers writing acceptance and integration tests.
- Coordinators/administrators evaluating functional coverage.
- College maintainers deciding deployment and operational constraints.

### 1.4 Definitions, Acronyms & Abbreviations

- MVP — Minimum Viable Product
- SIS — Student Information System
- API — Application Programming Interface
- FR — Functional Requirement
- NFR — Non-Functional Requirement
- P1..P6 — Period 1 through Period 6
- UTC — Coordinated Universal Time

### 1.5 References

- College daily timetable and roster provided by stakeholder (Appendix A)
- Timetable periods: 10:00–11:00 (P1), 11:00–12:00 (P2), 12:00–13:00 (P3), 13:00–13:40 (Lunch), 13:40–14:40 (P4), 14:40–15:40 (P5), 15:40–16:40 (P6)

---

## 2. Overall Description

### 2.1 System Context

The system is a web-based coordination layer around existing college schedules. It consumes CSV inputs for roster/timetable and exposes role-based front-ends. A lightweight backend processes approval workflows and broadcasts updates to teacher UIs.

Simple context diagram (textual):

```
+-----------+       +-----------+       +-----------+
|  Student  | <---> |  Backend  | <---> |  Teacher  |
|  Web App  |       |  API + RT |       |  Web App  |
+-----------+       +-----------+       +-----------+
                         ^  ^
                         |  |
                   +------------+
                   | Coordinator|
                   |   Web App  |
                   +------------+

CSV Imports -> Backend (Roster, Timetable, Teachers)
```

### 2.2 Actors and Stakeholders

- Student: submits letters, views status.
- Coordinator: reviews and approves/rejects submitted letters.
- Teacher: views and edits attendance for specific periods; receives notifications when approvals affect their period.
- Maintainer / Developer: uploads CSVs, modifies templates in code, performs deployments.
- System: automated processes (mapping, notifications, audit logging).

Stakeholders: Students, Teachers, Coordinator, College IT/Operations.

### 2.3 Product Perspective

The product is standalone with inputs from CSV and outputs viewed by teachers/coordinator/students. It is not initially integrated with a central SIS; CSV remains the authoritative import mechanism for roster/timetable.

### 2.4 Operating Environment

- Modern browsers (Chrome, Firefox, Edge, Safari) on desktop and mobile (responsive UI).
- Server environment: low-cost VPS or small cloud instance.
- Communication over HTTPS.

### 2.5 Design Constraints

- Monthly hosting and maintenance cost must aim to stay ≤ INR 5,000.
- Templates are edited through code-only workflows (maintainers deploy changes).
- Authentication for MVP uses pre-provisioned credentials configured on the server (passwords stored hashed).
- Real-time delivery target: notifications within 20 seconds.
- Support for poor connectivity: offline queuing and retry on clients.

### 2.6 Assumptions and Dependencies

- Rosters, timetables, and teacher mappings will be supplied as CSV files in formats defined in Appendix A.
- Day/time conventions are based on the college local timezone (no DST complexity expected).
- Single coordinator role (no federated approval workflow required in MVP).

---

## 3. External Interfaces

### 3.1 User Interfaces

Student UI (web, responsive)
- Dashboard: current letters and statuses.
- Template picker: select a template (prefilled fields: roll number, name, date/time slots).
- Editor: editable free-text body plus enforced structured fields (`start_datetime`, `end_datetime`, `event_name`, `roll_no`, `student_name`).
- Submit button with synchronous validation and offline queueing support.

Coordinator UI (web, responsive)
- Inbox: list of submitted letters (latest first) with search/filters (by status, date, student roll no).
- Letter detail view: full content, attachments (if any), approve/reject actions, optional comment.

Teacher UI (web, responsive)
- Period selector: choose a date and period (P1..P6).
- Attendance list: roster rows with `Present/Absent` toggles. Prefilled `Present` for students whose event was approved and map to that period; editable.
- Notification inbox / in-app toast for approvals affecting teacher periods.

### 3.2 Software Interfaces

- CSV import endpoints / admin UI for ingesting `roster.csv`, `timetable.csv`, `teachers.csv`.
- REST API for all persistent operations (letters, approvals, attendance). See Section 8 for sketch.

### 3.3 Communications Interfaces

- Real-time: WebSocket preferred; SSE acceptable. Fallback to client polling every 20s for poor connectivity.
- TLS required for all traffic.

---

## 4. Functional Requirements

Each FR is numbered, testable, and atomic.

### FR-01: CSV Roster Import
- Requirement: The system shall accept a CSV file with header `Roll Number,Name` and create student records. Duplicate roll numbers shall be rejected and reported.
- Priority: High
- Acceptance: Upload sample roster (Appendix A) → system creates 70 student records; duplicate rows reported with row numbers.

### FR-02: CSV Timetable Import
- Requirement: The system shall accept a timetable CSV using the header matching the college periods and persist day→period→subject mapping.
- Priority: High
- Acceptance: Import provided timetable; query returns Monday P1 = `SDMA`.

### FR-03: Teacher Mapping Import
- Requirement: The system shall accept `Subject,Teacher Name` CSV and map each subject to a teacher account.
- Priority: High
- Acceptance: Import teacher list; query subject `DE` returns `Prof. S. Lakshmi`.

### FR-04: Authentication (MVP)
- Requirement: The system shall authenticate users using a pre-provisioned credentials list (username/password) and only permit role-specific UI access.
- Priority: High
- Acceptance: Login succeeds with configured credentials; passwords stored hashed.

### FR-05: Templates & Letter Submission
- Requirement: Student UI shall expose templates containing pre-filled fields (roll_no, student_name) and required structured fields `event_name`, `start_datetime`, `end_datetime`. Students can edit the template and submit a letter to the coordinator.
- Priority: High
- Acceptance: Student submits a valid letter; letter appears in coordinator inbox as `Submitted`.

### FR-06: Letter Validation
- Requirement: Server shall validate `start_datetime < end_datetime` and that event overlaps at least one period; invalid letters rejected with meaningful messages.
- Priority: High
- Acceptance: Submitting `end_datetime` ≤ `start_datetime` returns a clear error.

### FR-07: Real-time Delivery to Coordinator
- Requirement: New submissions shall be delivered to the coordinator UI within 20 seconds (95th percentile).
- Priority: High
- Acceptance: Submit letter; coordinator sees it within 20s.

### FR-08: Approve/Reject by Coordinator
- Requirement: Coordinator can approve or reject a letter; approvals trigger attendance prefill for affected periods; rejections set letter status `Rejected`.
- Priority: High
- Acceptance: Coordinator approves; letter status updated with timestamp and comment recorded.

### FR-09: Event→Period Mapping Rule
- Requirement: Any overlap between the letter `start_datetime/end_datetime` interval and a period interval marks that entire period as affected.
- Priority: High
- Acceptance: Example: event 12:00–16:10 maps to P3..P6.

### FR-10: Teacher Attendance Prefill
- Requirement: On approval, the system shall pre-mark affected students as `Present` for each affected period in the teacher attendance UI. Prefill must be editable.
- Priority: High
- Acceptance: Teacher opens period attendance after approval; affected student appears pre-marked `Present`.

### FR-11: Teacher Edit & Audit
- Requirement: Teachers may modify any attendance mark; each change must be recorded in an audit log (actor, timestamp, prev/new value).
- Priority: High
- Acceptance: Change by teacher recorded in audit log and visible in administrative audit query.

### FR-12: Retroactive Approval Handling
- Requirement: If the coordinator approves after teacher finalized attendance, the system shall automatically update attendance to `Present` for affected student(s), notify the teacher, and create an audit record. Teachers can subsequently override.
- Priority: High
- Acceptance: Teacher finalizes absent; later approval updates to present and logs the automatic update.

### FR-13: Notifications to Teachers
- Requirement: Teachers shall receive in-app real-time notifications for approvals affecting their period(s) within 20 seconds.
- Priority: High
- Acceptance: Approval triggers teacher notification event within 20s.

### FR-14: Audit Log
- Requirement: System shall maintain an append-only audit log with: timestamp (UTC ISO8601), actor_id, action_type, target_resource, prev_value, new_value, comment. The log shall be queryable by date and actor.
- Priority: High
- Acceptance: Approve action creates audit row with all fields.

### FR-15: CSV Import Error Reporting
- Requirement: CSV import shall provide row-level error reporting listing row numbers and error messages for validation failures.
- Priority: Medium
- Acceptance: Import with malformed rows returns list of row errors.

### FR-16: Template Management (Code-Level)
- Requirement: Change to letter templates shall be done via code (developer maintainers) and deployed; no in-app template editor for MVP.
- Priority: Medium
- Acceptance: Template changes require code deployment.

### FR-17: Offline/Retry Behavior for Clients
- Requirement: Clients shall queue actions (submissions, approvals if coordinator offline, teacher edits) and retry when connectivity returns. UI must show sync status.
- Priority: Medium
- Acceptance: Submit while offline → queued; on reconnect submission transmitted and status updated.

### FR-18: Health Check Endpoint
- Requirement: System shall expose a `/health` endpoint returning HTTP 200 when core services are healthy.
- Priority: Low
- Acceptance: `GET /health` returns 200 under normal operation.

---

## 5. Non-Functional Requirements (NFRs)

NFRs are measurable and testable.

### NFR-01: Real-time Latency
- The system shall deliver real-time events (letter created, approved) to the intended recipients within 20 seconds (95th percentile).
- Test: Measure event delivery times in load tests; verify 95th percentile ≤ 20s.

### NFR-02: Concurrency & Throughput
- Support at least 2,500 concurrent users during peak windows without exceeding NFR-01 latency goal.
- Test: Load test with 2,500 concurrent simulated clients and measure throughput.

### NFR-03: UI Performance
- Teacher attendance UI rendering a roster of 70 students shall load and be interactive within 2 seconds on a 3G-equivalent connection (95th percentile).
- Test: Lighthouse or real-device tests with throttled network.

### NFR-04: API Response Times
- Read API calls must respond ≤ 500 ms (95th percentile) under normal load.
- Test: API latency monitoring over 24-hour period.

### NFR-05: Availability
- Target availability for the MVP: 99.0% (consider raising to 99.5% in production with budget review).
- Test: Measure uptime over 30-day period.

### NFR-06: Security
- All external traffic must use TLS. Passwords stored hashed (bcrypt/argon2). Admin/developer access limited to server controls.
- Rejection: Hardcoded credentials are permitted for MVP but must be stored hashed and documented as temporary.

### NFR-07: Data Integrity & Auditability
- Audit logs must be append-only and retained for at least 6 months (recommended). Audit queries must return results in <2s for 30-day ranges.

### NFR-08: Maintainability & Cost
- Architecture choices and managed services must aim to keep monthly hosting and maintenance ≤ INR 5,000.
- Recommendation: single small cloud VM, managed DB optional if within budget.

### NFR-09: Scalability
- System must be designed to allow horizontal scaling for real-time component and backend when funding allows.

### NFR-10: Accessibility & Usability
- Basic responsive design for mobile and desktop. Keyboard navigation and readable contrast for teacher workflows.

---

## 6. System Models (Use Cases & Interaction Flows)

### UC-01: Submit Event Letter (Student)
**Primary actor:** Student

**Preconditions:** Student record exists and user is authenticated.

**Main success scenario:**
1. Student logs in.
2. Student selects a template.
3. Student edits free-text fields and sets `start_datetime` and `end_datetime`.
4. Client validates fields; if offline, queue submission.
5. Client submits to backend.
6. Backend validates and stores letter with status `Submitted`.
7. Backend broadcasts `letter.created` event to coordinator clients.

**Postconditions:** Letter stored; coordinator notified.

**Failure paths:** Invalid datetime → client shows validation error. Server rejects malformed data → client displays server error.

### UC-02: Coordinator Review & Approve/Reject
**Primary actor:** Coordinator

**Main success scenario:**
1. Coordinator logs in.
2. Inbox displays `Submitted` letters.
3. Coordinator opens letter details.
4. Coordinator clicks `Approve`.
5. Backend computes affected periods (any overlap rule), stores approval, creates audit record, and broadcasts `letter.approved` event with affected periods.
6. Backend updates attendance prefill for affected teachers' periods.

**Alternate flows:** Reject → status `Rejected`; student UI updated.

### UC-03: Teacher Attendance Editing
**Primary actor:** Teacher

**Main success scenario:**
1. Teacher logs in and opens attendance for a period.
2. System loads roster for that class and period.
3. For students with approved events affecting this period, mark `Present` (prefill).
4. Teacher edits any marks and clicks `Save/Finalize`.
5. Backend persists changes and writes audit entries.

**Failure paths:** Network loss while saving → client queues edits and retries.

### UC-04: CSV Import (Maintainer)
**Primary actor:** Developer/Maintainer

**Main success scenario:**
1. Maintainer uploads CSV file.
2. System validates content and stores rows.
3. System returns a success summary or an error report with row numbers for failures.

**Failure paths:** Duplicate roll numbers → import aborted or partial (depending on chosen strategy). MVP: reject file and provide detailed error.

### UC-05: Retroactive Approval Handling
**Main success scenario:**
1. Teacher previously finalized attendance.
2. Coordinator approves a letter affecting that period.
3. System automatically updates attendance to `Present` for affected student(s), appends audit entry, and sends in-app notification to the teacher.
4. Teacher can override the automatically applied mark; override is recorded in audit log.

---

## 7. Data Model (Summary)

All attributes below include example data types.

- Student
  - `roll_number` (string, PK)
  - `name` (string)

- Teacher
  - `teacher_id` (UUID)
  - `name` (string)
  - `subjects` (array of subject codes)

- Subject
  - `code` (string)
  - `name` (string)
  - `teacher_id` (UUID)

- TimetableEntry
  - `day_of_week` (enum)
  - `period_index` (int 1..6)
  - `subject_code` (string)

- Letter
  - `id` (UUID)
  - `student_roll` (string)
  - `student_name` (string)
  - `event_name` (string)
  - `start_datetime` (ISO8601 string)
  - `end_datetime` (ISO8601 string)
  - `submitted_at` (ISO8601 string)
  - `status` (Submitted/Approved/Rejected)
  - `coordinator_comment` (string)

- AttendanceRecord
  - `id` (UUID)
  - `student_roll` (string)
  - `date` (YYYY-MM-DD)
  - `period_index` (int)
  - `mark` (Present/Absent)
  - `source` (Manual/SystemAuto)
  - `updated_by` (actor_id)
  - `updated_at` (ISO8601)
  - `version` (int)

- AuditLog
  - `id` (UUID)
  - `timestamp` (ISO8601)
  - `actor_id` (string)
  - `action` (string)
  - `target` (string)
  - `prev_value` (JSON)
  - `new_value` (JSON)
  - `comment` (string)

---

## 8. API & Real-time Events (MVP Sketch)

### REST API (examples)

- `POST /api/import/roster` — multipart/form-data CSV upload
  - Response: success summary or error report.

- `POST /api/letters`
  - Request body (JSON):

```json
{
  "student_roll": "24071A6601",
  "student_name": "Aarav Sharma",
  "event_name": "College Cultural Fest",
  "start_datetime": "2026-05-12T12:00:00",
  "end_datetime": "2026-05-12T16:10:00",
  "body": "(optional free text)"
}
```

- `GET /api/letters?status=Submitted` — returns list for coordinator
- `POST /api/letters/{id}/approve` — approves letter, requestor is coordinator; returns affected periods
- `GET /api/attendance?date=YYYY-MM-DD&period=3` — teacher period view
- `POST /api/attendance` — update attendance (bulk update allowed)

### Real-time events (WebSocket message types)

- `letter.created` — pushed to coordinator clients
  - Payload: `{ "letter_id": "...", "student_roll": "...", "submitted_at": "..." }`

- `letter.approved` — pushed to teacher clients for affected periods
  - Payload: `{ "letter_id": "...", "affected_periods": [{"date":"2026-05-12","period_index":3}], "student_roll": "..." }`

- `attendance.updated` — pushed to subscribed clients when attendance changes
  - Payload: `{ "date":"2026-05-12","period_index":3,"changes":[{"student_roll":"...","old":"Absent","new":"Present","actor":"system","ts":"..."}] }`

Transport recommendation: WebSocket + fallback polling (20s). Server should assign client subscriptions based on user role and the periods/subjects they handle.

---

## 9. Security, Privacy & Audit

### 9.1 Authentication & Authorization (MVP)

- Use pre-provisioned credentials stored in server configuration. Passwords must be stored salted and hashed (bcrypt/argon2). Even though credentials are preloaded, all authentication must be done via secure login endpoints.
- Each account shall be associated with one role: Student, Coordinator, or Teacher.

### 9.2 Transport & Data Protection

- HTTPS/TLS mandatory for all endpoints.
- Sensitive fields (passwords) not logged.

### 9.3 Audit Requirements

- All approval, attendance change, and import actions shall be recorded in the audit log with actor, timestamp, and previous/new values.
- Audit log should be append-only in design; at minimum, records should not be removed by regular operations.

### 9.4 Privacy

- PII is limited to student names and roll numbers. No sensitive health/payment data is stored in MVP.
- Retention policy: recommend 6–12 months for attendance and letters; confirm with college policy.

### 9.5 Security Risks & Mitigations

- Hardcoded credentials are a security risk — mitigate by hashing storage and planning for SSO/MFA in next release.
- Rate-limit authentication attempts to mitigate brute-force.

---

## 10. Edge Cases & Failure Handling

- **Late Approval After Finalized Attendance:** System auto-updates attendance and logs the change; teacher notified.
- **Partial Period Overlap:** Any overlap counts as full period affected (explicit rule).
- **Student Not in Roster:** Letter submission rejected with actionable error message; instruct contact to admin.
- **Duplicate Roll in CSV:** Import aborted with row-level error report.
- **No Teacher Mapping for Subject:** System flags the affected period and notifies maintainer. Teacher notification withheld until mapping is added or a fallback is specified.
- **Client Offline:** Queue actions in client storage and retry; sync status shown. Resolve conflicts via last-write-wins, but record both changes in audit.
- **Clock Skew / Timezone:** Server authoritative timezone (college local). Client should display times in local college timezone.

---

## 11. Testing & Acceptance Criteria

For each FR, acceptance tests are defined in Section 4. Additional testing recommendations:

- Unit tests for mapping logic (event interval → periods) and validation.
- Integration tests for end-to-end flow: submit letter → approve → teacher attendance prefill.
- Load testing: simulate 2,500 concurrent users; measure 95th percentile delivery latency for real-time events ≤ 20s.
- Security tests: password storage verification, TLS checks, auth rate limits.
- CSV import tests: valid and invalid inputs; ensure error reporting.

---

## 12. Deployment, Maintenance & Operational Notes

### 12.1 Suggested Architecture (cost-conscious MVP)

- Single small VPS (2 vCPU, 4GB RAM) hosting backend and WebSocket server.
- Small managed or self-hosted database (Postgres on same VPS or small managed tier). Consider separating DB when budget allows.
- Static assets served from the same VM or inexpensive CDN if required.
- TLS via Let's Encrypt.
- Regular backups (daily DB snapshot) with retention for 30 days.
- Health-check endpoint `/health` for monitoring.

### 12.2 Maintenance & Cost

- Choose lightweight frameworks and avoid expensive managed real-time services for MVP.
- Aim for monthly hosting ≤ INR 5,000. Document exact provider and costs before deployment.

### 12.3 Monitoring & Logging

- Basic metrics: request latency, error rate, WebSocket connection counts, queue lengths.
- Centralized logs (file rotated) and a simple alert for service down.

---

## 13. Risks and Mitigations

- **Security risk from hardcoded credentials:** Mitigate by hashing storage and planning SSO upgrade.
- **Budget constraints limiting HA options:** Accept reduced SLA for MVP and plan for funding for improved availability.
- **Real-time reliability under poor connectivity:** Implement robust offline queue and polling fallback.
- **Incorrect mapping due to timetable changes:** Provide easy CSV re-import and clear admin error reporting.

---

## 14. Open Issues

1. Data retention policy to be agreed (6 months recommended).
2. Timezone confirmation (assume college local time). Document explicit timezone in deployment.
3. Whether to allow batch approvals by coordinator (deferred).
4. Email/SMS notification for teachers (cost impact to evaluate).

---

## 15. Appendix

### A. Sample CSVs

#### A.1 Roster (header and sample rows)

```
Roll Number,Name
24071A6601,Aarav Sharma
24071A6602,Vivaan Reddy
24071A6603,Aditya Patel
24071A6604,Arjun Gupta
24071A6605,Reyansh Kumar
24071A6606,Muhammad Singh
24071A6607,Sai Verma
24071A6608,Krishna Nair
24071A6609,Ishaan Rao
24071A6610,Rohan Mehta
... (full roster provided by stakeholder)
```

#### A.2 Timetable (header and sample rows)

```
Day,10:00-11:00,11:00-12:00,12:00-1:00,1:00-1:40,1:40-2:40,2:40-3:40,3:40-4:40
Monday,SDMA,DE,DE,LUNCH,,DT,
Tuesday,,CD SE LAB,,LUNCH,SE,DE,
Wednesday,,DV LAB,,LUNCH,SE,ACD,DLDCO
Thursday,DLDCO,SIMA,ACD,LUNCH,,DE LAB,
Friday,SE,DLDCO,ACD,LUNCH,IPR,MTP,ECA CCA
Saturday,SIMA,ACD,SE,LUNCH,DLDCO,IPR,SPORTS
```

#### A.3 Teacher mapping

```
Subject,Teacher Name
SDMA,Dr. Ravi Kumar
DE,Prof. S. Lakshmi
CD SE LAB,Mr. Arjun Reddy
DV LAB,Ms. Neha Sharma
SE,Dr. Pooja Mehta
ACD,Prof. Kiran Nair
DLDCO,Dr. Anil Verma
SIMA,Ms. Kavya Iyer
DE LAB,Mr. Rohit Singh
IPR,Dr. Sneha Gupta
MTP,Prof. Vivek Joshi
ECA CCA,Ms. Ritu Kapoor
SPORTS,Mr. Manish Yadav
```

### B. Sample Letter Template (student view)

```
[Header: College Letterhead]

To
The Coordinator,
[College Name]

Subject: Permission to attend event — <EVENT_NAME>

Respected Sir/Madam,

I, <STUDENT_NAME> (Roll No: <ROLL_NO>), request permission to attend the following event:

Event Name: <EVENT_NAME>
From: <START_DATETIME>
To: <END_DATETIME>
Location: <LOCATION (optional)>

Brief reason / details: (editable free text)

I request you to kindly approve my leave for the above period and mark my attendance accordingly.

Thank you.

Yours faithfully,
<STUDENT_NAME>
<ROLL_NO>

[Submit]
```

### C. Sample Event → Period Mapping

College period intervals (local time):

- P1: 10:00–11:00
- P2: 11:00–12:00
- P3: 12:00–13:00
- Lunch: 13:00–13:40
- P4: 13:40–14:40
- P5: 14:40–15:40
- P6: 15:40–16:40

Example:

- Event: 2026-05-12 12:00 → 2026-05-12 16:10
- Overlaps P3, P4, P5, P6 → those periods considered affected.

---

### Document Revision History

- v1.0 — 2026-04-10 — Initial SRS prepared.

---

End of SRS
