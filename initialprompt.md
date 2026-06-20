# Initial Project Prompt

> This is the original specification prompt used to build the Budget Tracker MVP using
> a Spec-Driven Development approach. The full resulting specification is in
> [`app_spec.md`](app_spec.md). The application has been fully implemented as described.

---

You are an expert Python developer, Streamlit expert, and software architect. Your task is to build a secure, multi-user Budget Tracker MVP.

We will strictly follow a Spec-Driven Development approach. You must not write the core application code or Dockerfile until I have approved the initial specification.

### 1. Tech Stack & Environment
* **Language:** Python
* **Framework:** Streamlit
* **Package Manager:** `uv`
* **Containerization:** Docker (everything must run in a single container)
* **Storage:** Local JSON or Excel files (for this MVP phase)

### 2. Core Requirements
* **Multi-Tenant Data Isolation:** The app must support multiple users. Users must log in, and they must strictly only be able to view, edit, and access their own data.
* **Data Ingestion:** Users must be able to add expenses manually via a form OR upload a CSV/Excel file to bulk-import transactions.
* **Dashboards & Tracking:** The UI must include a dashboard overview showing income, expenses, and net savings. It must allow users to track specific expenses, view monthly summaries, and see their spending broken down by categories.

### 3. Security Best Practices (Mandatory)
Even though this is an MVP, you must implement the following security best practices:
* **Secure Authentication:** Passwords must NOT be stored in plain text. Use `bcrypt` or the `streamlit-authenticator` package to hash and verify user passwords.
* **Path Traversal Prevention:** Because user data is stored in local JSON/Excel files, you must strictly sanitize user IDs and usernames before using them to construct file paths. Ensure malicious users cannot use `../` to access other users' files.
* **Secure Session Management:** Use `st.session_state` properly to handle authentication state. Ensure that clearing the session logs the user out completely.
* **Docker Security:** Run the Streamlit process inside the Docker container as a non-root user.

### 4. Execution Plan (Spec-Driven Development)

**Step 1: Generate the Specification**
Create a detailed markdown specification document named `app_spec.md`. This document must outline:
* The data schema for how users (with hashed passwords), income, and expenses will be stored.
* The directory structure of the project.
* The UI flow and Streamlit page structure (e.g., Login, Dashboard, Add/Upload, Settings).
* Security considerations (how path traversal is prevented and how auth works).
* The `uv` dependency requirements.
Stop and ask for my approval on `app_spec.md` before proceeding.

**Step 2: Initialize the Project**
Once the spec is approved, initialize the project using `uv`. Set up the virtual environment, the `pyproject.toml`, and install the necessary dependencies (e.g., streamlit, streamlit-authenticator, bcrypt, pandas, openpyxl, plotly/altair).

**Step 3: Core Logic & Secure Storage**
Implement the data access layer. Create the functions to read/write the JSON/Excel files. Implement strict path sanitization to ensure the `user_id` or `username` acts as an impenetrable partition key.

**Step 4: Build the Streamlit UI**
Implement the Streamlit application based on the spec. Build the secure login flow first, followed by the uploaders, forms, and interactive charts.

**Step 5: Dockerization**
Create a secure, single `Dockerfile` that uses `uv` to install dependencies, creates a non-root user, and runs the Streamlit app on port 8501. Include a `docker-compose.yml` if necessary to map local volumes for persistent JSON/Excel storage.

Please begin with Step 1 and generate `app_spec.md`.
