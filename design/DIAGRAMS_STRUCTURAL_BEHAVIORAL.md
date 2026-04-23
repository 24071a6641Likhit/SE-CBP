# College Event Attendance System - StarUML Mermaid-Compatible Pack

This pack is adjusted to match StarUML Mermaid support constraints.
Supported diagram types used here are: classDiagram, sequenceDiagram, stateDiagram-v2, flowchart, erDiagram, requirementDiagram, and mindmap.

## 1. Use Case Diagram (flowchart representation)

```mermaid
flowchart LR
  Student[Student]
  Coordinator[Coordinator]
  Teacher[Teacher]
  Maintainer[Maintainer]

  U1[Submit Event Letter]
  U2[Track Letter Status]
  U3[Review Letter]
  U4[Approve Letter]
  U5[Reject Letter]
  U6[View Attendance]
  U7[Edit Attendance]
  U8[Import Roster]
  U9[Import Timetable]
  U10[Import Teacher Mapping]
  U11[Receive Realtime Updates]

  Student --> U1
  Student --> U2
  Coordinator --> U3
  Coordinator --> U4
  Coordinator --> U5
  Coordinator --> U11
  Teacher --> U6
  Teacher --> U7
  Teacher --> U11
  Maintainer --> U8
  Maintainer --> U9
  Maintainer --> U10
```

## 2. Class Diagram

```mermaid
classDiagram
  User <|-- Student
  User <|-- Teacher

  User : UUID id
  User : string username
  User : string password_hash
  User : string role
  User : datetime created_at

  Student : string roll_number
  Student : string name
  Student : UUID user_id

  Teacher : UUID teacher_id
  Teacher : string name
  Teacher : UUID user_id

  Subject : string code
  Subject : string name
  Subject : UUID teacher_id

  Timetable : int id
  Timetable : string day_of_week
  Timetable : int period_index
  Timetable : string subject_code

  Letter : UUID id
  Letter : string student_roll
  Letter : string student_name
  Letter : string event_name
  Letter : string content
  Letter : datetime start_datetime
  Letter : datetime end_datetime
  Letter : datetime submitted_at
  Letter : string status
  Letter : string coordinator_comment
  Letter : datetime approved_at
  Letter : UUID approved_by

  AttendanceRecord : UUID id
  AttendanceRecord : string student_roll
  AttendanceRecord : date date
  AttendanceRecord : int period_index
  AttendanceRecord : string mark
  AttendanceRecord : string source
  AttendanceRecord : UUID updated_by
  AttendanceRecord : datetime updated_at
  AttendanceRecord : int version

  AuditLog : UUID id
  AuditLog : datetime ts
  AuditLog : UUID actor_id
  AuditLog : string action
  AuditLog : string target
  AuditLog : json prev_value
  AuditLog : json new_value
  AuditLog : string comment

  Student "1" --> "0..*" Letter : submits
  Teacher "1" --> "0..*" Subject : teaches
  Subject "1" --> "0..*" Timetable : maps_to
  Student "1" --> "0..*" AttendanceRecord : has
  User "1" --> "0..*" AuditLog : actor
```

## 3. Sequence Diagram

```mermaid
sequenceDiagram
  participant StudentUI
  participant Backend
  participant DB
  participant CoordinatorUI
  participant TeacherUI

  StudentUI->>Backend: POST /api/letters
  Backend->>DB: Insert letter Submitted
  DB->>Backend: OK
  Backend->>CoordinatorUI: letter.created

  CoordinatorUI->>Backend: POST /api/letters/{id}/approve
  Backend->>DB: Update letter Approved
  Backend->>DB: Upsert attendance Present
  Backend->>DB: Insert audit records
  DB->>Backend: OK

  Backend->>TeacherUI: letter.approved
  TeacherUI->>Backend: ack event_id
  TeacherUI->>Backend: POST /api/attendance
  Backend->>DB: Update attendance + audit
  DB->>Backend: OK
```

## 4. Statechart Diagram

```mermaid
stateDiagram-v2
  [*] --> Submitted
  Submitted --> Approved: approve
  Submitted --> Rejected: reject
  Approved --> [*]
  Rejected --> [*]
```

## 5. Activity Diagram (flowchart representation)

```mermaid
flowchart TD
  A[Start] --> B[Receive request]
  B --> C{Payload valid}
  C -->|No| D[Return 400]
  C -->|Yes| E{Teacher authorized}
  E -->|No| F[Return 403]
  E -->|Yes| G{Attendance exists}
  G -->|No| H[Create attendance]
  G -->|Yes| I{Version match}
  I -->|No| J[Return 409]
  I -->|Yes| K[Update attendance]
  H --> L[Insert audit]
  K --> L
  L --> M[Commit]
  M --> N[Return success]
  D --> O[End]
  F --> O
  J --> O
  N --> O
```

## 6. Package Diagram (flowchart representation)

```mermaid
flowchart LR
  P1[frontend package]
  P2[backend.app package]
  P3[data contracts package]

  P1 --> P2
  P2 --> P3
```

## 7. Component Diagram (flowchart representation)

```mermaid
flowchart LR
  C1[Frontend Web App]
  C2[Auth Component]
  C3[Letter Component]
  C4[Attendance Component]
  C5[Import Component]
  C6[Realtime Component]
  C7[Audit Component]
  C8[Database]

  C1 --> C2
  C1 --> C3
  C1 --> C4
  C1 --> C5
  C1 --> C6
  C2 --> C8
  C3 --> C8
  C4 --> C8
  C5 --> C8
  C6 --> C8
  C7 --> C8
  C3 --> C7
  C4 --> C7
```

## 8. Deployment Diagram (flowchart representation)

```mermaid
flowchart LR
  N1[Client Browser]
  N2[Frontend Server]
  N3[Backend FastAPI Uvicorn]
  N4[Database SQLite or Postgres]

  N1 --> N2
  N1 --> N3
  N3 --> N4
```

## 9. Object Diagram (classDiagram instance style)

```mermaid
classDiagram
  class "studentA:Student" as studentA {
    string roll_number
    string name
  }

  class "letterL1:Letter" as letterL1 {
    string id
    string status
    string event_name
  }

  class "attP3:AttendanceRecord" as attP3 {
    date date
    int period_index
    string mark
    string source
  }

  class "coordU:User" as coordU {
    string username
    string role
  }

  studentA --> letterL1 : submitted
  coordU --> letterL1 : approved_by
  letterL1 --> attP3 : affects
```

## 10. Interaction Overview Diagram (flowchart representation)

```mermaid
flowchart TD
  I1[Submit letter]
  I2{Validation success}
  I3[Coordinator review]
  I4{Approve or reject}
  I5[Notify rejection]
  I6[Auto update attendance]
  I7[Teacher ack and optional edit]
  I8[End]

  I1 --> I2
  I2 --> I3
  I2 --> I8
  I3 --> I4
  I4 --> I5
  I4 --> I6
  I5 --> I8
  I6 --> I7
  I7 --> I8
```

## 11. Communication Diagram (flowchart representation)

```mermaid
flowchart LR
  O1[StudentUI]
  O2[Backend]
  O3[DB]
  O4[CoordinatorUI]
  O5[TeacherUI]

  O1 --> O2
  O2 --> O3
  O2 --> O4
  O4 --> O2
  O2 --> O3
  O2 --> O5
  O5 --> O2
```

## 12. Entity Relationship Diagram

```mermaid
erDiagram
  USERS ||--o| STUDENTS : account
  USERS ||--o| TEACHERS : account
  TEACHERS ||--o{ SUBJECTS : teaches
  SUBJECTS ||--o{ TIMETABLE : mapped
  STUDENTS ||--o{ LETTERS : submits
  STUDENTS ||--o{ ATTENDANCE_RECORDS : has
  USERS ||--o{ LETTERS : approves
  USERS ||--o{ ATTENDANCE_RECORDS : updates
  USERS ||--o{ AUDIT_LOG : writes

  USERS {
    uuid id
    string username
    string role
  }
  STUDENTS {
    string roll_number
    string name
    uuid user_id
  }
  TEACHERS {
    uuid teacher_id
    string name
    uuid user_id
  }
  SUBJECTS {
    string code
    string name
    uuid teacher_id
  }
  TIMETABLE {
    int id
    string day_of_week
    int period_index
    string subject_code
  }
  LETTERS {
    uuid id
    string student_roll
    string status
    datetime submitted_at
  }
  ATTENDANCE_RECORDS {
    uuid id
    string student_roll
    date date
    int period_index
    string mark
    string source
    int version
  }
  AUDIT_LOG {
    uuid id
    datetime ts
    string action
    string target
  }
```

## 13. Requirement Diagram

```mermaid
requirementDiagram
  requirement FR_01 {
    id: FR-01
    text: Import roster CSV and create student records.
    risk: medium
    verifymethod: test
  }

  requirement FR_08 {
    id: FR-08
    text: Coordinator can approve or reject letters.
    risk: high
    verifymethod: test
  }

  requirement FR_10 {
    id: FR-10
    text: Attendance is prefilled for approved events.
    risk: high
    verifymethod: test
  }

  element BackendService {
    type: software
  }

  BackendService - satisfies -> FR_01
  BackendService - satisfies -> FR_08
  BackendService - satisfies -> FR_10
```

## 14. Mindmap

```mermaid
mindmap
  root((College Event Attendance))
    Structural
      Class Diagram
      Package Diagram
      Component Diagram
      Deployment Diagram
      ER Diagram
      Object Diagram
    Behavioral
      Use Case Diagram
      Sequence Diagram
      Statechart Diagram
      Activity Diagram
      Interaction Overview
      Communication Diagram
    Requirements
      FR-01 Import
      FR-08 Approval
      FR-10 Prefill
    Realtime
      WebSocket events
      Ack handling
```

## 15. System Context Diagram (additional)

```mermaid
flowchart LR
  A[Student UI]
  B[Coordinator UI]
  C[Teacher UI]
  D[Maintainer]
  E[Backend API]
  F[Realtime WS]
  G[Database]
  H[CSV Files]

  A --> E
  B --> E
  C --> E
  D --> E
  A --> F
  B --> F
  C --> F
  E --> G
  D --> H
  H --> E
```
