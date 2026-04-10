# Frontend API Documentation

## Base URL
- Local: `http://localhost:8000`
- API prefix: `/api`

## Authentication
Most endpoints require Clerk bearer token.

- Header: `Authorization: Bearer <token>`
- `Content-Type: application/json`

## Standard Error Shape
```json
{ "detail": "Error message" }
```

## Health
### `GET /health`
```json
{ "status": "healthy" }
```

## User API
### `POST /api/user/sync`
Request:
```json
{
  "department": "Software Engineering",
  "role": "student"
}
```

Response `200`:
```json
{
  "id": "uuid",
  "email": "user@cloud.neduet.edu.pk",
  "department": "Software Engineering",
  "role": "student",
  "status": "active"
}
```

### `GET /api/settings/form-deadline`
Auth: required

Returns the form deadline as a date string. Any authenticated user can read it.

Response `200`:
```json
{
  "deadline": "2026-04-30"
}
```

If the setting has not been created yet:
```json
{
  "deadline": null
}
```

### `PUT /api/admin/settings/form-deadline`
Auth: admin only

Creates or updates the `form_deadline` global setting.

Request:
```json
{
  "deadline_timestamp": 1777507200
}
```

The timestamp may be in seconds or milliseconds.

Response `200`:
```json
{
  "setting_key": "form_deadline",
  "deadline": "2026-04-30"
}
```

## CV API
Base path: `/api/cv-submissions`

### Create/Update Payload Compatibility
Both snake_case and camelCase are accepted for key fields.

Accepted examples:
- `personal_info` or `personalInfo`
- `career_counseling` or `careerCounseling`
- `student_image` / `studentImage` / `student_image_url` / `studentImageUrl`
- `industrial_visits` or `industrialVisits`
- `extra_curricular` or `extraCurricular`
- `father_name` or `fatherName`
- `roll_no` or `rollNo`
- internships date keys: `from_date`/`to_date` or `from`/`to`
- industrial visit date keys: `visit_date` or `date`

Date values accepted:
- `YYYY-MM-DD`
- `Oct, 2023` / `October, 2023` / `Oct 2023` / `October 2023`
- empty string `""` is treated as `null`

Sections supporting string arrays or object arrays:
- `certificates`: `["AWS"]` or `[{"name":"AWS"}]`
- `achievements`: `["Winner"]` or `[{"description":"Winner"}]`
- `skills`: `["Python"]` or `[{"name":"Python"}]`
- `extraCurricular`: `["Cricket"]` or `[{"activity":"Cricket"}]`

### Complete Create/Update Payload Example
```json
{
  "studentImage": "https://example.com/student.png",
  "careerCounseling": false,
  "personalInfo": {
    "name": "Ali Khan",
    "fatherName": "Ahmed Khan",
    "department": "Software Engineering",
    "batch": "2024",
    "cell": "03123456789",
    "rollNo": "SE123456",
    "cnic": "42101-1234567-1",
    "email": "ali@cloud.neduet.edu.pk",
    "gender": "Male",
    "dob": "2002-09-14",
    "address": "Karachi"
  },
  "academics": [
    {
      "degree": "BE",
      "university": "NED",
      "year": "2026",
      "from": "2022-01-01",
      "to": "2026-12-31",
      "gpa": "3.45",
      "majors": "Civil Engineering"
    }
  ],
  "internships": [
    {
      "organization": "ABC Tech",
      "position": "Intern",
      "field": "Backend",
      "duties": ["API development", "Testing"],
      "from": "2023-06-01",
      "to": "2023-08-31"
    }
  ],
  "industrialVisits": [
    {
      "organization": "Toyota",
      "purpose": "Production line study",
      "date": "Oct, 2023"
    }
  ],
  "fyp": {
    "title": "CV Automation",
    "company": "NED",
    "objectives": "Automate CV workflows"
  },
  "certificates": ["AWS Cloud Practitioner"],
  "achievements": ["Hackathon winner"],
  "skills": ["Python", "FastAPI"],
  "extraCurricular": ["Debate"],
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
Create CV (student only). Returns full CV object.

### `GET /api/cv-submissions/`
List CVs (admin/advisor only). Returns full CV objects with an additional `summary` block.

### `GET /api/cv-submissions/me`
List current student CVs. Returns full CV objects.

### `GET /api/cv-submissions/{cv_id}`
Get one CV by ID. Returns full CV object.

### `PUT /api/cv-submissions/{cv_id}`
Update CV (student owner only). Returns updated full CV object.

### `DELETE /api/cv-submissions/{cv_id}`
```json
{ "message": "CV '<cv_id>' deleted successfully" }
```

### `POST /api/cv-submissions/{cv_id}/approve`
```json
{
  "cv_id": "uuid",
  "status": "approved",
  "message": "CV approved successfully"
}
```

### `POST /api/cv-submissions/{cv_id}/reject`
Request:
```json
{ "comments": "Please improve project details." }
```

Response:
```json
{
  "cv_id": "uuid",
  "status": "rejected",
  "rejection_comment": "Please improve project details.",
  "message": "CV rejected successfully"
}
```

### Complete CV Response Object
```json
{
  "cv_id": "uuid",
  "student_id": "uuid",
  "student_email": "user@cloud.neduet.edu.pk",
  "status": "pending_advisor",
  "student_image": "https://example.com/student.png",
  "rejection_comment": null,
  "career_counseling": false,
  "created_at": "2026-03-09T10:35:00.000000",
  "updated_at": "2026-03-09T10:35:00.000000",
  "personal_info": {
    "id": "uuid",
    "cv_id": "uuid",
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
      "id": "uuid",
      "cv_id": "uuid",
      "degree": "BE",
      "university": "NED",
      "year": "2026",
      "from_date": "2022-01-01",
      "to_date": "2026-12-31",
      "gpa": "3.45",
      "majors": "Civil Engineering"
    }
  ],
  "internships": [
    {
      "id": "uuid",
      "cv_id": "uuid",
      "organization": "ABC Tech",
      "position": "Intern",
      "field": "Backend",
      "duties": ["API development", "Testing"],
      "from_date": "2023-06-01",
      "to_date": "2023-08-31"
    }
  ],
  "industrial_visits": [
    {
      "id": "uuid",
      "cv_id": "uuid",
      "organization": "Toyota",
      "purpose": "Production line study",
      "visit_date": "2023-10-01"
    }
  ],
  "fyp": {
    "id": "uuid",
    "cv_id": "uuid",
    "title": "CV Automation",
    "company": "NED",
    "objectives": "Automate CV workflows"
  },
  "certificates": [{ "id": "uuid", "cv_id": "uuid", "name": "AWS" }],
  "achievements": [{ "id": "uuid", "cv_id": "uuid", "description": "Winner" }],
  "skills": [{ "id": "uuid", "cv_id": "uuid", "name": "Python" }],
  "extra_curricular": [{ "id": "uuid", "cv_id": "uuid", "activity": "Debate" }],
  "references": [
    {
      "id": "uuid",
      "cv_id": "uuid",
      "name": "Dr. Example",
      "contact": "03001234567",
      "occupation": "Professor",
      "relation": "Mentor"
    }
  ]
}
```

List response (`GET /api/cv-submissions/`) includes all above fields plus:
```json
{
  "summary": {
    "cv_id": "uuid",
    "student_email": "user@cloud.neduet.edu.pk",
    "department": "Software Engineering",
    "batch": "2024",
    "cv_status": "pending_advisor",
    "skills": ["Python"],
    "cgpa": "3.45",
    "internships_count": 1
  }
}
```

## Admin API
Base path: `/api/admin`

### `GET /api/admin/advisors/pending`
Response includes advisor creation time:
```json
[
  {
    "id": "uuid",
    "email": "advisor@cloud.neduet.edu.pk",
    "department": "Software Engineering",
    "created_at": "2026-03-09T10:35:00.000000"
  }
]
```

### `POST /api/admin/advisors/{advisor_id}/approve`
```json
{ "message": "Advisor approved successfully" }
```

### `POST /api/admin/advisors/{advisor_id}/reject`
```json
{ "message": "Advisor rejected successfully" }
```

## Clerk Webhook API
### `POST /webhooks/clerk`
Used by Clerk only.

Expected events:
- `user.created`
- `user.updated`
- `user.deleted`

Success:
```json
{ "status": "success" }
```
