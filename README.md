BASE URL
http://localhost:8080
1. POST /insert
Purpose: add one patient row and obtain triage prediction.
Input (JSON array)
Content-Type: application/json
Body: 9-element list, exact order & types
JSON
Copy

[
  "Male",                       // gender          string  ["Male"|"Female"]
  55,                           // age             int     0-120
  "Chest tightness",            // ChiefComplaint  string  any free text
  7,                            // PainGrade       int     1-5
  140,                          // BP systolic     int     50-250
  90,                           // BP diastolic    int     30-150
  95,                           // PulseRate       int     40-200
  22,                           // Respiration     int     8-50
  98                            // O2Saturation    int     70-100
]

Expected Output (JSON, 201 Created)
JSON
Copy

{
  "id": 3,            // int   primary key assigned by DB
  "triage_level": 0   // int   0 = not-urgent, 1 = urgent
}

Error Responses
400 Bad Request – payload not a 9-element list
500 Internal Server Error – any other problem (details in "error" field)
2. GET /records
Purpose: retrieve stored patient rows.
Query Parameters
limit (optional) – integer ≥ 0, default 0 (=all)
Expected Output (JSON, 200 OK)
Array of objects, newest first:
JSON
Copy

[
  {
    "id": 3,
    "gender": "Male",
    "age": 55,
    "ChiefComplaint": "Chest tightness",
    "PainGrade": 7,
    "BloodPressure_high": 140,
    "BloodPressure_low": 90,
    "PulseRate": 95,
    "Respiration": 22,
    "O2Saturation": 98,
    "TriageLevel": 0,
    "created_at": "2025-12-03 14:23:45"
  }
]

Error Responses
500 – DB or server error (details in "error")


