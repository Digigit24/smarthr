# SmartHR-In — Frontend API Reference

> **Base URL:** `http://localhost:8000` (dev) · All API routes prefix: `/api/v1/`
> **Auth:** `Authorization: Bearer <access_token>` on every request
> **Tenant:** injected from JWT — no extra header needed (super-admins may pass `X-Tenant-Id`)
> **Content-Type:** `application/json`

---

## 1. Authentication Flow

SmartHR-In has **no local auth**. The frontend authenticates against the SuperAdmin service and passes its JWT to every SmartHR-In request.

```
1. POST https://admin.celiyo.com/api/auth/login/
   { "email": "...", "password": "..." }
   → { user, tokens: { access, refresh } }

2. Store tokens.access → use as Bearer token for all /api/v1/* calls
3. If 401 received → refresh via SuperAdmin refresh endpoint or re-login
```

**JWT payload fields SmartHR-In reads:**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | Actor ID for all mutations |
| `email` | string | Actor email |
| `tenant_id` | UUID | All data scoped to this |
| `tenant_slug` | string | Tenant slug |
| `is_super_admin` | bool | If true, can pass `X-Tenant-Id` override |
| `permissions` | object | `{ "smarthrin.jobs.view": true\|false\|"all"\|"own" }` |
| `enabled_modules` | string[] | Must contain `"smarthrin"` or 403 |

---

## 2. Global Response Shapes

### Paginated List
```json
{
  "count": 142,
  "next": "http://localhost:8000/api/v1/jobs/?page=2",
  "previous": null,
  "results": [ ...items ]
}
```
Default page size: **20**, max: **100**. Use `?page=N` to paginate.

### Error
```json
{
  "error": "Human-readable message",
  "code": "SNAKE_CASE_CODE",
  "details": {}
}
```

Common codes: `NO_AUTH`, `TOKEN_EXPIRED`, `INVALID_TOKEN`, `MODULE_NOT_ENABLED`, `PERMISSION_DENIED`, `NOT_FOUND`, `VALIDATION_ERROR`

---

## 3. Enums Reference

| Model | Field | Values |
|-------|-------|--------|
| Job | `job_type` | `FULL_TIME` `PART_TIME` `CONTRACT` `INTERNSHIP` |
| Job | `experience_level` | `ENTRY` `MID` `SENIOR` `LEAD` |
| Job | `status` | `DRAFT` `OPEN` `PAUSED` `CLOSED` |
| Applicant | `source` | `MANUAL` `WEBSITE` `LINKEDIN` `REFERRAL` `IMPORT` |
| Application | `status` | `APPLIED` `AI_SCREENING` `AI_COMPLETED` `SHORTLISTED` `INTERVIEW_SCHEDULED` `INTERVIEWED` `OFFER` `HIRED` `REJECTED` `WITHDRAWN` |
| CallRecord | `provider` | `OMNIDIM` `BOLNA` |
| CallRecord | `status` | `QUEUED` `INITIATED` `RINGING` `IN_PROGRESS` `COMPLETED` `FAILED` `NO_ANSWER` `BUSY` |
| Scorecard | `recommendation` | `STRONG_YES` `YES` `MAYBE` `NO` `STRONG_NO` |
| Interview | `interview_type` | `AI_VOICE` `HR_SCREEN` `TECHNICAL` `CULTURE_FIT` `FINAL` |
| Interview | `status` | `SCHEDULED` `CONFIRMED` `IN_PROGRESS` `COMPLETED` `CANCELLED` `NO_SHOW` |
| Notification | `notification_type` | `EMAIL` `WHATSAPP` `IN_APP` |
| Notification | `category` | `APPLICATION` `INTERVIEW` `CALL` `SYSTEM` |
| Activity | `verb` | `CREATED` `UPDATED` `DELETED` `STATUS_CHANGED` `PUBLISHED` `CLOSED` `TRIGGERED_CALL` `CALL_COMPLETED` `CALL_FAILED` `INTERVIEW_SCHEDULED` `INTERVIEW_COMPLETED` `INTERVIEW_CANCELLED` `SCORECARD_CREATED` `NOTE_ADDED` `BULK_ACTION` |

---

## 4. Recruitment Pipeline Flow

```
[DRAFT job] → publish → [OPEN job]
                              ↓
              Applicant submits → Application [APPLIED]
                              ↓
              change-status → [AI_SCREENING]  ← triggers AI call automatically
                              ↓
              call completes → [AI_COMPLETED]  (scorecard created)
                              ↓
              score ≥ 7.0   → [SHORTLISTED]   (auto)
              score < 4.0   → [REJECTED]      (auto)
                              ↓
              schedule interview → [INTERVIEW_SCHEDULED]
                              ↓
              complete interview → [INTERVIEWED]
                              ↓
              [OFFER] → [HIRED]
```

---

## 5. Jobs — `/api/v1/jobs/`

**Permission prefix:** `smarthrin.jobs.*`

### 5.1 List Jobs
```
GET /api/v1/jobs/
```
**Query params:** `status` · `department` · `location` · `search` · `ordering` · `page`

**Response 200** (paginated `JobListItem`):
```json
{
  "id": "uuid",
  "title": "Senior Python Developer",
  "department": "Engineering",
  "location": "Remote",
  "job_type": "FULL_TIME",
  "experience_level": "SENIOR",
  "status": "OPEN",
  "application_count": 12,
  "voice_agent_id": "agent-uuid-or-null",
  "published_at": "2026-03-01T10:00:00Z",
  "closes_at": "2026-04-01T00:00:00Z",
  "created_at": "2026-02-28T09:00:00Z"
}
```

### 5.2 Create Job
```
POST /api/v1/jobs/
```
**Body:**
```json
{
  "title": "Senior Python Developer",
  "department": "Engineering",
  "location": "Remote",
  "job_type": "FULL_TIME",
  "experience_level": "SENIOR",
  "salary_min": "80000.00",
  "salary_max": "120000.00",
  "description": "We are hiring...",
  "requirements": "5+ years Python...",
  "status": "DRAFT",
  "voice_agent_id": "agent-uuid",
  "voice_agent_config": {
    "auto_shortlist_threshold": 7.0,
    "auto_reject_threshold": 4.0
  },
  "published_at": null,
  "closes_at": "2026-06-01T00:00:00Z"
}
```
**Response 201** → `JobDetail` (see §5.3)

### 5.3 Get Job
```
GET /api/v1/jobs/{id}/
```
**Response 200** (`JobDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "title": "Senior Python Developer",
  "department": "Engineering",
  "location": "Remote",
  "job_type": "FULL_TIME",
  "experience_level": "SENIOR",
  "salary_min": "80000.00",
  "salary_max": "120000.00",
  "description": "...",
  "requirements": "...",
  "status": "OPEN",
  "application_count": 12,
  "voice_agent_id": "uuid-or-null",
  "voice_agent_config": {},
  "published_at": "2026-03-01T10:00:00Z",
  "closes_at": "2026-04-01T00:00:00Z",
  "created_at": "2026-02-28T09:00:00Z",
  "updated_at": "2026-03-01T10:00:00Z"
}
```

### 5.4 Update Job
```
PUT  /api/v1/jobs/{id}/   → full replace (same body as Create)
PATCH /api/v1/jobs/{id}/  → partial (any subset of fields)
```
**Response 200** → `JobDetail`

### 5.5 Delete Job
```
DELETE /api/v1/jobs/{id}/
```
**Response 204** (no body)

### 5.6 Publish Job
```
POST /api/v1/jobs/{id}/publish/
```
Sets `status → OPEN`, sets `published_at` if not already set.
**Response 200** → `JobDetail`

### 5.7 Close Job
```
POST /api/v1/jobs/{id}/close/
```
Sets `status → CLOSED`.
**Response 200** → `JobDetail`

### 5.8 List Job Applications
```
GET /api/v1/jobs/{id}/applications/
```
Returns paginated `ApplicationListItem` for this job. Same shape as §8.1.

### 5.9 Job Stats (all jobs in tenant)
```
GET /api/v1/jobs/stats/
```
**Response 200:**
```json
{
  "total_applications": 142,
  "avg_score": 6.84,
  "by_status": {
    "APPLIED": 40,
    "AI_SCREENING": 5,
    "SHORTLISTED": 30,
    "HIRED": 12,
    "REJECTED": 55
  }
}
```

---

## 6. Applicants — `/api/v1/applicants/`

**Permission prefix:** `smarthrin.applicants.*`

### 6.1 List Applicants
```
GET /api/v1/applicants/
```
**Query params:** `source` · `search` (first_name, last_name, email) · `ordering` · `page`

**Response 200** (paginated `ApplicantListItem`):
```json
{
  "id": "uuid",
  "first_name": "Alice",
  "last_name": "Johnson",
  "full_name": "Alice Johnson",
  "email": "alice@example.com",
  "phone": "+14155550001",
  "source": "LINKEDIN",
  "skills": ["Python", "Django"],
  "experience_years": 5,
  "current_role": "Backend Engineer",
  "current_company": "Acme Inc",
  "tags": ["senior", "remote-ok"],
  "created_at": "2026-03-01T09:00:00Z"
}
```

### 6.2 Create Applicant
```
POST /api/v1/applicants/
```
**Body:**
```json
{
  "first_name": "Alice",
  "last_name": "Johnson",
  "email": "alice@example.com",
  "phone": "+14155550001",
  "resume_url": "https://cdn.example.com/resume.pdf",
  "linkedin_url": "https://linkedin.com/in/alice",
  "portfolio_url": "",
  "skills": ["Python", "Django", "PostgreSQL"],
  "experience_years": 5,
  "current_company": "Acme Inc",
  "current_role": "Backend Engineer",
  "notes": "Referred by John",
  "source": "LINKEDIN",
  "tags": ["senior", "remote-ok"]
}
```
**Response 201** → `ApplicantDetail` (see §6.3)

### 6.3 Get Applicant
```
GET /api/v1/applicants/{id}/
```
**Response 200** (`ApplicantDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "first_name": "Alice",
  "last_name": "Johnson",
  "full_name": "Alice Johnson",
  "email": "alice@example.com",
  "phone": "+14155550001",
  "resume_url": "https://...",
  "linkedin_url": "https://...",
  "portfolio_url": "",
  "skills": ["Python", "Django"],
  "experience_years": 5,
  "current_company": "Acme Inc",
  "current_role": "Backend Engineer",
  "notes": "",
  "source": "LINKEDIN",
  "tags": [],
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-01T09:00:00Z"
}
```

### 6.4 Update / Delete Applicant
```
PUT   /api/v1/applicants/{id}/   → same body as Create
PATCH /api/v1/applicants/{id}/   → partial
DELETE /api/v1/applicants/{id}/  → 204
```

### 6.5 Applicant's Applications
```
GET /api/v1/applicants/{id}/applications/
```
Returns paginated `ApplicationListItem` for this applicant.

---

## 7. Pipeline Stages — `/api/v1/pipeline/`

**Permission prefix:** `smarthrin.pipeline.*`
> Seed default stages on tenant setup before creating applications.

### 7.1 List Stages
```
GET /api/v1/pipeline/
```
**Response 200** (paginated, ordered by `order` asc):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "name": "Shortlisted",
  "slug": "shortlisted",
  "order": 2,
  "color": "#3b82f6",
  "is_default": true,
  "is_terminal": false,
  "auto_action": {},
  "created_at": "...",
  "updated_at": "..."
}
```

### 7.2 Create Stage
```
POST /api/v1/pipeline/
```
**Body:**
```json
{
  "name": "Background Check",
  "slug": "background-check",
  "order": 4,
  "color": "#f59e0b",
  "is_default": false,
  "is_terminal": false,
  "auto_action": {}
}
```
**Response 201** → `PipelineStage`

### 7.3 Update / Delete Stage
```
PUT   /api/v1/pipeline/{id}/
PATCH /api/v1/pipeline/{id}/
DELETE /api/v1/pipeline/{id}/  → 204
```

### 7.4 Reorder Stages
```
POST /api/v1/pipeline/reorder/
```
**Body:**
```json
{ "stage_ids": ["uuid-1", "uuid-2", "uuid-3"] }
```
Sets `order = 0, 1, 2...` for each ID in sequence.
**Response 200** → full ordered list of all `PipelineStage`

### 7.5 Seed Default Stages
```
POST /api/v1/pipeline/seed-defaults/
```
No body. Creates 7 default stages if not already present:
Applied (0) · AI Screening (1) · Shortlisted (2) · Interview (3) · Offer (4) · Hired (5) · Rejected (6)
**Response 200** → full list of all stages

---

## 8. Applications — `/api/v1/applications/`

**Permission prefix:** `smarthrin.applications.*`

### 8.1 List Applications
```
GET /api/v1/applications/
```
**Query params:** `status` · `job_id` · `applicant_id` · `search` · `ordering` (created_at, score, status) · `page`

**Response 200** (paginated `ApplicationListItem`):
```json
{
  "id": "uuid",
  "job_id": "uuid",
  "job_title": "Senior Python Developer",
  "applicant_id": "uuid",
  "applicant_name": "Alice Johnson",
  "applicant_email": "alice@example.com",
  "status": "SHORTLISTED",
  "score": "7.50",
  "created_at": "2026-03-05T10:00:00Z",
  "updated_at": "2026-03-06T08:00:00Z"
}
```

### 8.2 Create Application
```
POST /api/v1/applications/
```
**Body (existing applicant):**
```json
{
  "job": "job-uuid",
  "applicant": "applicant-uuid",
  "status": "APPLIED",
  "notes": "",
  "metadata": {}
}
```
**Body (inline new applicant — creates Applicant + Application atomically):**
```json
{
  "job": "job-uuid",
  "applicant": {
    "first_name": "Bob",
    "last_name": "Smith",
    "email": "bob@example.com",
    "phone": "+14155550002",
    "source": "WEBSITE"
  }
}
```
**Response 201** → `ApplicationDetail` (see §8.3)

### 8.3 Get Application
```
GET /api/v1/applications/{id}/
```
**Response 200** (`ApplicationDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "job_id": "uuid",
  "job": {
    "id": "uuid", "title": "Senior Python Developer",
    "department": "Engineering", "location": "Remote",
    "job_type": "FULL_TIME", "experience_level": "SENIOR", "status": "OPEN"
  },
  "applicant_id": "uuid",
  "applicant": {
    "id": "uuid", "first_name": "Alice", "last_name": "Johnson",
    "email": "alice@example.com", "phone": "+14155550001",
    "skills": ["Python"], "experience_years": 5,
    "current_role": "Backend Engineer", "current_company": "Acme",
    "source": "LINKEDIN"
  },
  "status": "SHORTLISTED",
  "score": "7.50",
  "rejection_reason": "",
  "notes": "",
  "metadata": {},
  "call_records": [ ...CallRecordSummary ],
  "scorecards": [ ...ScorecardSummary ],
  "interviews": [ ...InterviewSummary ],
  "created_at": "...",
  "updated_at": "..."
}
```

**`CallRecordSummary` fields:** `id` `provider` `provider_call_id` `phone` `status` `duration` `summary` `recording_url` `started_at` `ended_at` `created_at`

**`ScorecardSummary` fields:** `id` `communication_score` `knowledge_score` `confidence_score` `relevance_score` `overall_score` `recommendation` `summary` `strengths` `weaknesses` `created_at`

**`InterviewSummary` fields:** `id` `interview_type` `scheduled_at` `duration_minutes` `interviewer_name` `interviewer_email` `status` `meeting_link` `feedback` `rating` `created_at`

### 8.4 Update Application
```
PUT   /api/v1/applications/{id}/
PATCH /api/v1/applications/{id}/
```
**Body (writable fields):** `job` · `applicant` · `status` · `score` · `rejection_reason` · `notes` · `metadata`

### 8.5 Delete Application
```
DELETE /api/v1/applications/{id}/  → 204
```

### 8.6 Change Status
```
POST /api/v1/applications/{id}/change-status/
```
**Body:**
```json
{
  "status": "SHORTLISTED",
  "reason": ""
}
```
> Setting `status: "AI_SCREENING"` automatically queues an AI voice call.

**Response 200** → `ApplicationDetail`

### 8.7 Trigger AI Screening Call
```
POST /api/v1/applications/{id}/trigger-ai-call/
```
No body. Immediately dispatches an AI call (job must have `voice_agent_id`, applicant must have valid `phone`).

**Response 201:**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "provider": "OMNIDIM",
  "status": "QUEUED",
  "phone": "+14155550001",
  "voice_agent_id": "agent-uuid",
  "provider_call_id": "",
  "created_at": "2026-03-10T09:00:00Z"
}
```

### 8.8 Bulk Action
```
POST /api/v1/applications/bulk-action/
```
**Body:**
```json
{
  "application_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "action": "change_status",
  "status": "REJECTED"
}
```
**Response 200:**
```json
{ "updated": 3, "action": "change_status" }
```

---

## 9. Call Records — `/api/v1/calls/`

**Permission prefix:** `smarthrin.calls.*`
Call records are **read-only** (created automatically by AI screening).

### 9.1 List Calls
```
GET /api/v1/calls/
```
**Query params:** `status` · `application_id` · `ordering` (created_at, started_at) · `page`

**Response 200** (paginated `CallRecordListItem`):
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "provider": "OMNIDIM",
  "status": "COMPLETED",
  "phone": "+14155550001",
  "duration": 312,
  "summary": "Candidate demonstrated strong Python skills...",
  "started_at": "2026-03-10T09:05:00Z",
  "ended_at": "2026-03-10T09:10:12Z",
  "created_at": "2026-03-10T09:00:00Z",
  "provider_call_id": "omnidim-call-xyz",
  "voice_agent_id": "agent-uuid"
}
```

### 9.2 Get Call Detail
```
GET /api/v1/calls/{id}/
```
**Response 200** (`CallRecordDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "application_id": "uuid",
  "provider": "OMNIDIM",
  "voice_agent_id": "agent-uuid",
  "provider_call_id": "omnidim-call-xyz",
  "phone": "+14155550001",
  "status": "COMPLETED",
  "duration": 312,
  "transcript": "AI: Hello Alice...\nAlice: Hi, yes...",
  "recording_url": "https://cdn.example.com/recordings/call.mp3",
  "summary": "Strong candidate...",
  "raw_response": {},
  "started_at": "2026-03-10T09:05:00Z",
  "ended_at": "2026-03-10T09:10:12Z",
  "error_message": "",
  "created_at": "...",
  "updated_at": "...",
  "scorecard": {
    "id": "uuid",
    "communication_score": "8.50",
    "knowledge_score": "7.00",
    "confidence_score": "9.00",
    "relevance_score": "7.50",
    "overall_score": "8.00",
    "recommendation": "YES",
    "summary": "...",
    "strengths": ["Clear communication"],
    "weaknesses": ["Limited cloud experience"],
    "detailed_feedback": {}
  }
}
```

### 9.3 Get Call Transcript
```
GET /api/v1/calls/{id}/transcript/
```
**Response 200:**
```json
{ "transcript": "AI: Hello...\nCandidate: Hi..." }
```

### 9.4 Retry Failed Call
```
POST /api/v1/calls/{id}/retry/
```
Only works when `status = "FAILED"`.
**Response 200** → `CallRecordDetail` (new call record)
**Response 400** if not FAILED: `{ "detail": "Only FAILED calls can be retried." }`

### 9.5 Available Voice Agents
```
GET /api/v1/calls/available-agents/
```
Returns active voice agents from the Voice AI Orchestrator.
**Response 200:**
```json
[
  {
    "id": "agent-uuid",
    "name": "HR Screener - Engineering",
    "provider": "OMNIDIM",
    "is_active": true,
    "description": "Screens for backend engineering roles",
    "created_at": "2026-01-15T00:00:00Z"
  }
]
```

---

## 10. Scorecards — `/api/v1/scorecards/`

**Permission prefix:** `smarthrin.calls.*`
Scorecards are **read-only** (created automatically after call completes).

### 10.1 List Scorecards
```
GET /api/v1/scorecards/
```
**Query params:** `application_id` · `ordering` (overall_score, created_at) · `page`

**Response 200** (paginated `ScorecardListItem`):
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "overall_score": "8.00",
  "communication_score": "8.50",
  "knowledge_score": "7.00",
  "confidence_score": "9.00",
  "relevance_score": "7.50",
  "recommendation": "YES",
  "summary": "Strong candidate with clear communication.",
  "created_at": "2026-03-10T09:15:00Z"
}
```

### 10.2 Get Scorecard Detail
```
GET /api/v1/scorecards/{id}/
```
**Response 200** (`ScorecardDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "application_id": "uuid",
  "call_record_id": "uuid",
  "communication_score": "8.50",
  "knowledge_score": "7.00",
  "confidence_score": "9.00",
  "relevance_score": "7.50",
  "overall_score": "8.00",
  "summary": "Strong candidate...",
  "strengths": ["Clear communication", "Deep Python knowledge"],
  "weaknesses": ["Limited AWS experience"],
  "recommendation": "YES",
  "detailed_feedback": {
    "communication": "Spoke clearly and concisely...",
    "knowledge": "Demonstrated solid fundamentals..."
  },
  "created_at": "...",
  "updated_at": "..."
}
```

> **Auto-routing thresholds** (configurable in `job.voice_agent_config`):
> `overall_score ≥ 7.0` → Application → `SHORTLISTED`
> `overall_score < 4.0` → Application → `REJECTED`
> `4.0 ≤ overall_score < 7.0` → Application → `AI_COMPLETED` (manual review)

---

## 11. Interviews — `/api/v1/interviews/`

**Permission prefix:** `smarthrin.interviews.*`

### 11.1 List Interviews
```
GET /api/v1/interviews/
```
**Query params:** `status` · `application_id` · `interview_type` · `search` (interviewer_name, email) · `ordering` (scheduled_at, created_at) · `page`

**Response 200** (paginated `InterviewListItem`):
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "interview_type": "TECHNICAL",
  "scheduled_at": "2026-03-15T14:00:00Z",
  "duration_minutes": 60,
  "interviewer_name": "John Doe",
  "interviewer_email": "john@company.com",
  "status": "SCHEDULED",
  "meeting_link": "https://meet.google.com/abc-def",
  "created_at": "2026-03-10T10:00:00Z"
}
```

### 11.2 Create Interview
```
POST /api/v1/interviews/
```
**Body:**
```json
{
  "application": "application-uuid",
  "interview_type": "TECHNICAL",
  "scheduled_at": "2026-03-15T14:00:00Z",
  "duration_minutes": 60,
  "interviewer_user_id": "user-uuid-or-null",
  "interviewer_name": "John Doe",
  "interviewer_email": "john@company.com",
  "meeting_link": "https://meet.google.com/abc-def",
  "calendar_event_id": ""
}
```
**Response 201** → `InterviewDetail`

### 11.3 Get Interview
```
GET /api/v1/interviews/{id}/
```
**Response 200** (`InterviewDetail`):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "application_id": "uuid",
  "interview_type": "TECHNICAL",
  "scheduled_at": "2026-03-15T14:00:00Z",
  "duration_minutes": 60,
  "interviewer_user_id": "uuid-or-null",
  "interviewer_name": "John Doe",
  "interviewer_email": "john@company.com",
  "status": "SCHEDULED",
  "meeting_link": "https://meet.google.com/abc-def",
  "calendar_event_id": "",
  "feedback": "",
  "rating": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### 11.4 Update / Delete Interview
```
PUT   /api/v1/interviews/{id}/
PATCH /api/v1/interviews/{id}/
DELETE /api/v1/interviews/{id}/  → 204
```

### 11.5 Cancel Interview
```
POST /api/v1/interviews/{id}/cancel/
```
No body. Sets `status → CANCELLED`.
**Response 200** → `InterviewDetail`

### 11.6 Complete Interview
```
POST /api/v1/interviews/{id}/complete/
```
**Body (all optional):**
```json
{
  "feedback": "Candidate showed excellent problem-solving skills.",
  "rating": 4
}
```
Sets `status → COMPLETED`. Rating is 1–5.
**Response 200** → `InterviewDetail`

---

## 12. Analytics — `/api/v1/analytics/`

**Permission prefix:** `smarthrin.analytics.view`

### 12.1 Dashboard Metrics
```
GET /api/v1/analytics/dashboard/
```
**Response 200:**
```json
{
  "total_jobs_open": 8,
  "total_applications": 142,
  "total_calls_completed": 89,
  "avg_candidate_score": 6.84,
  "applications_today": 3,
  "calls_today": 5,
  "shortlisted_count": 22,
  "offers_count": 4,
  "hiring_conversion_rate": 8.45
}
```

### 12.2 Application Funnel
```
GET /api/v1/analytics/funnel/
```
**Response 200:**
```json
[
  { "status": "APPLIED", "count": 40 },
  { "status": "AI_SCREENING", "count": 5 },
  { "status": "AI_COMPLETED", "count": 10 },
  { "status": "SHORTLISTED", "count": 22 },
  { "status": "INTERVIEW_SCHEDULED", "count": 8 },
  { "status": "HIRED", "count": 12 },
  { "status": "REJECTED", "count": 45 }
]
```

### 12.3 Score Distribution
```
GET /api/v1/analytics/scores/
```
**Response 200:**
```json
[
  { "range": "0-10", "count": 0 },
  { "range": "10-20", "count": 2 },
  { "range": "30-40", "count": 5 },
  { "range": "60-70", "count": 18 },
  { "range": "70-80", "count": 31 },
  { "range": "80-90", "count": 20 },
  { "range": "90-100", "count": 13 }
]
```

### 12.4 Activity Timeline
```
GET /api/v1/analytics/timeline/?period=30d
```
**Query params:** `period` → `7d` `30d` `90d` (default: `30d`)

**Response 200:**
```json
[
  { "date": "2026-03-01", "applications": 5, "calls": 3, "hires": 1 },
  { "date": "2026-03-02", "applications": 8, "calls": 6, "hires": 0 }
]
```

---

## 13. Notifications — `/api/v1/notifications/`

**Returns only notifications for the authenticated user.**

### 13.1 List Notifications
```
GET /api/v1/notifications/
```
**Response 200** (paginated):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "owner_user_id": "uuid",
  "recipient_user_id": "uuid",
  "notification_type": "IN_APP",
  "category": "APPLICATION",
  "title": "Candidate Shortlisted",
  "message": "Alice Johnson has been shortlisted for Senior Python Developer.",
  "data": { "application_id": "uuid" },
  "is_read": false,
  "read_at": null,
  "sent_at": "2026-03-10T09:15:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

### 13.2 Get Notification
```
GET /api/v1/notifications/{id}/
```
**Response 200** → same shape as list item

### 13.3 Mark Single Notification Read
```
PATCH /api/v1/notifications/{id}/read/
```
No body.
**Response 200** → `Notification` (with `is_read: true`, `read_at: "..."`)

### 13.4 Mark All Notifications Read
```
POST /api/v1/notifications/read-all/
```
No body.
**Response 200:**
```json
{ "marked_read": 14 }
```

---

## 14. Activity Log — `/api/v1/activities/`

**Read-only audit trail for the tenant.**

### 14.1 List Activities
```
GET /api/v1/activities/
```
**Query params:**
`verb` · `resource_type` (Job, Application, CallRecord, Interview, Scorecard, Applicant) · `resource_id` · `actor_user_id` · `created_at_gte` · `created_at_lte` · `ordering` · `page`

**Response 200** (paginated, newest first):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "actor_user_id": "uuid",
  "actor_email": "recruiter@company.com",
  "verb": "STATUS_CHANGED",
  "resource_type": "Application",
  "resource_id": "uuid",
  "resource_label": "Alice Johnson → Senior Python Developer [SHORTLISTED]",
  "before": { "status": "AI_COMPLETED" },
  "after": { "status": "SHORTLISTED" },
  "metadata": { "reason": "" },
  "created_at": "2026-03-10T09:20:00Z"
}
```

### 14.2 Get Activity
```
GET /api/v1/activities/{id}/
```
**Response 200** → same shape as list item

---

## 15. Webhooks — `/webhooks/`

> **No JWT auth required.** Called by the Voice AI Orchestrator.
> Protected by HMAC-SHA256 signature in `X-Webhook-Signature` header.

### 15.1 Call Completed
```
POST /webhooks/voice/call-completed/
```
**Payload from Voice AI Orchestrator:**
```json
{
  "provider_call_id": "omnidim-call-xyz",
  "transcript": "AI: Hello...",
  "duration": 312,
  "recording_url": "https://cdn.omnidim.io/rec/xyz.mp3",
  "summary": "Candidate showed strong skills...",
  "score": {
    "communication": 8.5,
    "knowledge": 7.0,
    "confidence": 9.0,
    "relevance": 7.5,
    "overall": 8.0,
    "strengths": ["Clear communication"],
    "weaknesses": ["Limited AWS"],
    "recommendation": "YES",
    "detailed_feedback": {}
  },
  "metadata": { "applicationId": "uuid", "jobId": "uuid" }
}
```
**Response 200:** `{ "status": "processed", "call_record_id": "uuid" }`

### 15.2 Call Status Update
```
POST /webhooks/voice/call-status/
```
**Payload:**
```json
{
  "call_id": "omnidim-call-xyz",
  "status": "ringing"
}
```
`status` values: `initiated` `ringing` `in_progress` `completed` `failed` `no_answer` `busy`
**Response 200:** `{ "status": "updated", "call_record_id": "uuid" }`

---

## 16. Schema / Docs

```
GET /api/schema/        → OpenAPI 3.0 YAML schema
GET /api/docs/          → Swagger UI (interactive)
GET /api/redoc/         → Redoc UI
GET /health/            → { status: "healthy", version, timestamp }
```

---

## 17. Recommended Frontend Setup Flow

```
1. Auth
   POST admin.celiyo.com/api/auth/login/ → store access token

2. Bootstrap (first tenant setup)
   POST /api/v1/pipeline/seed-defaults/    → create default stages
   GET  /api/v1/calls/available-agents/    → load voice agents for job config

3. Create a Job
   POST /api/v1/jobs/                      → status: DRAFT, set voice_agent_id
   POST /api/v1/jobs/{id}/publish/         → status → OPEN

4. Add Candidates
   POST /api/v1/applicants/                → create applicant record
   POST /api/v1/applications/              → link applicant to job

5. AI Screening
   POST /api/v1/applications/{id}/change-status/  { status: "AI_SCREENING" }
   # Call fires automatically → poll call status
   GET  /api/v1/calls/?application_id={id}        → watch status
   GET  /api/v1/scorecards/?application_id={id}   → read scorecard when COMPLETED

6. Interview
   POST /api/v1/interviews/                        → schedule interview
   POST /api/v1/interviews/{id}/complete/          → submit feedback + rating

7. Decision
   POST /api/v1/applications/{id}/change-status/  { status: "HIRED" }

8. Dashboard
   GET /api/v1/analytics/dashboard/
   GET /api/v1/analytics/funnel/
   GET /api/v1/analytics/timeline/?period=30d

9. Notifications (poll or websocket proxy)
   GET /api/v1/notifications/             → unread badge count via response.count
   PATCH /api/v1/notifications/{id}/read/
   POST  /api/v1/notifications/read-all/
```

---

## 18. Permissions Quick Reference

| Action | Required Permission |
|--------|-------------------|
| View jobs | `smarthrin.jobs.view` |
| Create / edit jobs | `smarthrin.jobs.create` / `smarthrin.jobs.edit` |
| Delete job | `smarthrin.jobs.delete` |
| View applicants | `smarthrin.applicants.view` |
| Create / edit applicants | `smarthrin.applicants.create` / `smarthrin.applicants.edit` |
| View applications | `smarthrin.applications.view` |
| Create / edit applications | `smarthrin.applications.create` / `smarthrin.applications.edit` |
| Trigger AI call | `smarthrin.calls.create` |
| View calls / scorecards | `smarthrin.calls.view` |
| View interviews | `smarthrin.interviews.view` |
| Create / edit interviews | `smarthrin.interviews.create` / `smarthrin.interviews.edit` |
| View pipeline | `smarthrin.pipeline.view` |
| Edit pipeline | `smarthrin.pipeline.edit` |
| View analytics | `smarthrin.analytics.view` |
| View activities | `smarthrin.activities.view` |

Permission values in JWT: `false` (denied) · `true` / `"all"` (full access) · `"own"` (own records only) · `"team"` (team records)

---

*Generated for SmartHR-In API v1.0.0 — backend branch `claude/build-smarthr-backend-HzpLY`*
