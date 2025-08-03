* Workforce Management API

This is a Spring Boot application for managing employee tasks in a logistics company. It is designed for use by managers and operations staff to create, assign, and track tasks for field staff.

*  How to Run

*  Requirements
- Java 17
- Gradle
- Android Studio (or any compatible IDE)
- Internet connection for dependency download

*  Setup Steps

1. Clone or download the project
2. Open the folder in Android Studio
3. Ensure 'build.gradle' includes:
   '''groovy
   implementation 'org.mapstruct:mapstruct:1.5.3.Final'
   annotationProcessor 'org.mapstruct:mapstruct-processor:1.5.3.Final'
4. Sync Gradle

5. Run the main class:
     com.railse.hiring.workforcemgmt.WorkforcemgmtApplication
The API will be available at: 'http://localhost:8080'

*  API Endpoints

* --> Get Task by ID

curl --location 'http://localhost:8080/task-mgmt/1'
--> Create Task

curl --location 'http://localhost:8080/task-mgmt/create' \
--header 'Content-Type: application/json' \
--data '{
  "requests": [
    {
      "reference_id": 105,
      "reference_type": "ORDER",
      "task": "CREATE_INVOICE",
      "assignee_id": 1,
      "priority": "HIGH",
      "task_deadline_time": 1728192000000
    }
  ]
}'
--> Update Task Status
curl --location 'http://localhost:8080/task-mgmt/update' \
--header 'Content-Type: application/json' \
--data '{
  "requests": [
    {
      "task_id": 1,
      "task_status": "STARTED",
      "description": "Work has been started."
    }
  ]
}'
--> Assign Tasks by Reference (Bug Fix #1 tested here)

curl --location 'http://localhost:8080/task-mgmt/assign-by-ref' \
--header 'Content-Type: application/json' \
--data '{
  "reference_id": 201,
  "reference_type": "ENTITY",
  "assignee_id": 5
}'
--> Fetch Tasks by Date Range (Bug Fix #2 tested here)

curl --location 'http://localhost:8080/task-mgmt/fetch-by-date/v2' \
--header 'Content-Type: application/json' \
--data '{
  "start_date": 1672531200000,
  "end_date": 1735689599000,
  "assignee_ids": [1, 2]
}'


6. The server runs at: http://localhost:8080


* Features Implemented

- Create new tasks
- Update task status and description
- Assign task by reference (fixes duplicate bug)
- Filter out cancelled tasks when fetching
- Smart "Today's Work" view for operations
- Priority-based task creation
- Task retrieval by ID

* API Endpoints

* Get Task by ID

curl --location 'http://localhost:8080/task-mgmt/1'

* Create New Task

curl --location 'http://localhost:8080/task-mgmt/create' \
--header 'Content-Type: application/json' \
--data '{
"requests": [
{
"reference_id": 105,
"reference_type": "ORDER",
"task": "CREATE_INVOICE",
"assignee_id": 1,
"priority": "HIGH",
"task_deadline_time": 1728192000000
}
]
}'

* Update Task Status and Description

curl --location 'http://localhost:8080/task-mgmt/update' \
--header 'Content-Type: application/json' \
--data '{
"requests": [
{
"task_id": 1,
"task_status": "STARTED",
"description": "Work has been started."
}
]
}'

* Assign Tasks by Reference
This endpoint fixes the bug where old tasks were not removed. It cancels existing assignments and creates a new one.

curl --location 'http://localhost:8080/task-mgmt/assign-by-ref' \
--header 'Content-Type: application/json' \
--data '{
"reference_id": 201,
"reference_type": "ENTITY",
"assignee_id": 5
}'

* Fetch Tasks by Date Range
This endpoint filters out cancelled tasks and implements the Smart Daily View logic.

curl --location 'http://localhost:8080/task-mgmt/fetch-by-date/v2' \
--header 'Content-Type: application/json' \
--data '{
"start_date": 1672531200000,
"end_date": 1735689599000,
"assignee_ids": [1, 2]
}'

* Technologies Used

- Java 17
- Spring Boot 3.4.8
- Lombok
- MapStruct
- Gradle
- In-memory storage (Map<Long, TaskManagement>) — no database required

* Notes

- The application uses seed data pre-loaded into memory when it starts.
- No real database is connected. All tasks are stored in a temporary memory map.
- Task responses are returned in a consistent JSON format, including 'data', 'status', and 'pagination' fields.
