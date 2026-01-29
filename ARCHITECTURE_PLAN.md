# Architecture Plan: Dictionary App 2.0 (Django Edition)

## 1. Overview
We are transforming the HTML prototype into a robust **Django** web application.
**Goal**: Full user management (Login/Register), Database storage, and AI integration.

## 2. Tech Stack (Python Powered)
Django is a "batteries-included" framework, making it perfect for rapid development.

- **Backend**: **Django** (Python).
  - Handles URL routing, API logic, and Database interactions.
  - **Built-in Admin Panel**: deeply useful for managing words/users without code.
  - **Built-in Authentication**: Login/Register/Logout is ready out of the box.
- **Frontend**: **Django Templates** + **TailwindCSS** + **JavaScript**.
  - We will reuse your existing nice `index.html` but make it "dynamic".
  - Usage of `Alpine.js` or standard JS (like you have) for the interactive parts.
- **Database**: **PostgreSQL** (Production) / **SQLite** (Development).
  - Django switches between these easily.
- **AI Integration**: **Perplexity API**.
  - Python has excellent libraries (`requests` or `openai` client) to call the API.

## 3. Deployment (DigitalOcean)
- **Droplet**: Ubuntu server.
- **Server Software**: Gunicorn (Python server) + Nginx (Web interface).
- **Database**: PostgreSQL installed on the same droplet or a managed database.

---

## 4. User Flow

### A. Authentication (Built-in)
1. User goes to `/login` or `/register`.
2. Django handles password hashing and session cookies automatically.
3. Once logged in, user sees only *their* words.

### B. AI Auto-Fill
1. User types word.
2. JS sends AJAX request to Django view: `/api/generate_definition/`.
3. Django calls **Perplexity API**.
4. JSON response typically contains:
    ```json
    {
      "ru": "...",
      "pos": "...",
      "example": "..."
    }
    ```
5. Frontend fills the inputs.

---

## 5. Roadmap (Django)
1. **Setup**: Install `django`, `psycopg2`, `requests`. Create project `vocab_app`.
2. **Models**: Create `Word` model (word, translation, example, user_link).
3. **Views**: Create views for the Index page and the API endpoint.
4. **Templates**: Adapt your `index.html` to inherit from a base Django template.
5. **AI**: Write the Python function to query Perplexity.
6. **Deploy**: Setup DigitalOcean droplet.

### Ready to init the Django project?
