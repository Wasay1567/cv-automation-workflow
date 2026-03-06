# Frontend API Documentation

## Base URL
- Local: `http://localhost:8000`
- API prefix: `/api`

## Authentication
Most API endpoints require Clerk Bearer token.

- Header: `Authorization: Bearer <token>`
- `Content-Type: application/json`

Protected groups:
- CV endpoints: authenticated user required
- User sync endpoint: authenticated user required
- Admin endpoints: authenticated + active admin required

Public groups:
- Health endpoint
- Clerk webhook endpoint (called by Clerk)

## Enums Used in Responses
- User role: `student | advisor | admin`
- User status: `active | inactive | rejected`
- CV status: `draft | submitted | pending_advisor | approved | rejected`

## Standard Error Shape
```json
{ "detail": "Error message" }
```

## Health
### `GET /health`
Response `200`
```json
{ "status": "healthy" }
```

## User API
### `POST /api/user/sync`
Sync user profile preferences for current authenticated Clerk user.

Request body:
```json
{
  "department": "Software Engineering",
  "role": "student"
}
```

Response `200`:
```json
{
  "id": "f8f6b140-8a74-4bca-8f74-b3a61fd0d766",
  "email": "user@cloud.neduet.edu.pk",
  "department": "Software Engineering",
  "role": "student",
  "status": "active"
}
```

Possible errors:
- `401` invalid/missing token
- `404` user not found in DB

## CV API
Base path: `/api/cv-submissions`

### CV Create/Update Request Body
Used by both create and update.

```json
{
  "career_counseling": false,
  "personal_info": {
    "name": "Ali Khan",
    "father_name": "Ahmed Khan",
    "department": "Software Engineering",
    "batch": "2024",
    "cell": "03123456789",
    "roll_no": "SE123456",
    "cnic": "42101-1234567-1",
    "email": "ali@cloud.neduet.edu.pk",
    "gender": "Male",
    "dob": "2002-09-14",
    "address": "Karachi"
  },
  "academics": [
    {
      "degree": "BS Software Engineering",
      "university": "NED University",
      "year": "2024",
      "gpa": "3.45",
      "majors": "Computer Science"
    }
  ],
  "internships": [
    {
      "organization": "ABC Tech",
      "position": "Backend Intern",
      "field": "Backend",
      "from_date": "2023-06-01",
      "to_date": "2023-08-31"
    }
  ],
  "industrial_visits": [
    {
      "organization": "PTCL",
      "purpose": "Learning visit",
      "visit_date": "2023-11-01"
    }
  ],
  "fyp": {
    "title": "CV Automation",
    "company": "NED",
    "objectives": "Automate CV workflows"
  },
  "certificates": [
    { "name": "AWS Cloud Practitioner" }
  ],
  "achievements": [
    { "description": "Hackathon winner" }
  ],
  "skills": [
    { "name": "Python" },
    { "name": "FastAPI" }
  ],
  "extra_curricular": [
    { "activity": "Debate society" }
  ],
  "references": [
    {
      "name": "Dr. Example",
      "contact": "03001234567",
      "occupation": "Professor",
      "relation": "Mentor"
    }
  ]
}
```

### `POST /api/cv-submissions/`
Create CV. Student only.

Response `201`: full CV object.

### `GET /api/cv-submissions/`
List CV summaries. Admin and advisor only.

Response `200`:
```json
[
  {
    "cv_id": "f87e6f02-6c16-44da-a4f8-1527dfd386d8",
    "student_email": "student@cloud.neduet.edu.pk",
    "department": "Software Engineering",
    "batch": "2024",
    "cv_status": "pending_advisor",
    "skills": ["Python", "FastAPI"],
    "cgpa": "3.45",
    "internships_count": 1
  }
]
```

### `GET /api/cv-submissions/me`
Get all CVs of current student. Student only.

Response `200`: array of full CV objects.

### `GET /api/cv-submissions/{cv_id}`
Get one CV by id.

Response `200`: full CV object.

### `PUT /api/cv-submissions/{cv_id}`
Update a CV. Student owner only. Uses same body as create.

Response `200`: updated full CV object.

### `DELETE /api/cv-submissions/{cv_id}`
Delete a CV. Student owner only.

Response `200`:
```json
{ "message": "CV '<cv_id>' deleted successfully" }
```

### `POST /api/cv-submissions/{cv_id}/approve`
Approve CV. Admin/advisor only.

Response `200`:
```json
{
  "cv_id": "f87e6f02-6c16-44da-a4f8-1527dfd386d8",
  "status": "approved",
  "message": "CV approved successfully"
}
```

### `POST /api/cv-submissions/{cv_id}/reject`
Reject CV with optional comment. Admin/advisor only.

Request body:
```json
{ "comments": "Please improve project details." }
```

Response `200`:
```json
{
  "cv_id": "f87e6f02-6c16-44da-a4f8-1527dfd386d8",
  "status": "rejected",
  "rejection_comment": "Please improve project details.",
  "message": "CV rejected successfully"
}
```

### Full CV Object Shape
Returned by create, get, update, and `GET /me`.

```json
{
  "cv_id": "uuid",
  "student_id": "uuid",
  "student_email": "user@cloud.neduet.edu.pk",
  "status": "pending_advisor",
  "rejection_comment": null,
  "career_counseling": false,
  "created_at": "2026-03-06T10:35:00.000000",
  "updated_at": "2026-03-06T10:35:00.000000",
  "personal_info": { "...": "..." },
  "academics": [],
  "internships": [],
  "industrial_visits": [],
  "fyp": null,
  "certificates": [],
  "achievements": [],
  "skills": [],
  "extra_curricular": [],
  "references": []
}
```

Common CV errors:
- `401` invalid/missing token
- `403` role not allowed
- `404` CV not found or not accessible

## Admin API
Base path: `/api/admin`

### `GET /api/admin/advisors/pending`
Get all pending advisors (role `advisor`, status `inactive`).

Response `200`:
```json
[
  {
    "id": "uuid",
    "email": "advisor@cloud.neduet.edu.pk",
    "department": "Software Engineering"
  }
]
```

### `POST /api/admin/advisors/{advisor_id}/approve`
Approve advisor.

Response `200`:
```json
{ "message": "Advisor approved successfully" }
```

### `POST /api/admin/advisors/{advisor_id}/reject`
Reject advisor.

Response `200`:
```json
{ "message": "Advisor rejected successfully" }
```

Common admin errors:
- `401` invalid/missing token
- `403` admin access required or admin account not active
- `404` advisor not found or already processed

## Clerk Webhook API
### `POST /webhooks/clerk`
Used by Clerk only.

Expected events:
- `user.created`
- `user.updated`
- `user.deleted`

Success response:
```json
{ "status": "success" }
```

Possible ignore responses:
```json
{
  "status": "ignored",
  "reason": "invalid_email_domain",
  "detail": "Only '@cloud.neduet.edu.pk' emails are allowed"
}
```

```json
{
  "status": "ignored",
  "reason": "unsupported_event_type",
  "event_type": "..."
}
```

Possible webhook errors:
- `400` invalid webhook signature or payload
- `409` DB constraint conflicts
- `500` webhook secret missing
