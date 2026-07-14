# DeepBlue Supply API

The **DeepBlue Supply API** is a containerized, AI-enhanced microservice designed to optimize marine and offshore asset management. In the maritime and oil & gas industries, maintenance lead times and unplanned asset downtimes can cost operators hundreds of thousands of dollars per hour. This API solves these inefficiencies by structuring unstructured technician field notes, identifying maintenance/part requirements, and automating inventory tracking in real time.

---

## 1. System Architecture

The microservice is designed for containerized deployment, ensuring reliability, scalability, and ease of setup in isolated environments (such as offshore vessels or onshore command centers).

```
                      +------------------------------------------+
                      |               Web Client                 |
                      +--------------------+---------------------+
                                           |
                                   REST HTTP / JSON
                                           v
    +--------------------------------------+--------------------------------------+
    | Docker Compose                       |                                      |
    |                                      v                                      |
    |   +----------------------------------+----------------------------------+   |
    |   | FastAPI Web Service (Port 8000)                                     |   |
    |   |                                                                     |   |
    |   |   +-------------------+    +-------------------+                    |   |
    |   |   |   Assets Router   |    |  Inventory Router |                    |   |
    |   |   +-------------------+    +-------------------+                    |   |
    |   |                                                                     |   |
    |   |   +-------------------+    +-------------------+                    |   |
    |   |   | Maintenance Router|    |  GenAI Extractor  |                    |   |
    |   |   +-------------------+    +-------------------+                    |   |
    |   +-------------------+--------------------+----------------------------+   |
    |                       |                    |                                |
    |                   SQL Alchemy             REST API Calls                    |
    |                       v                    v                                |
    |   +-------------------+----+       +-------+------------+                   |
    |   | PostgreSQL Database    |       | External LLM Provider|                  |
    |   | (Port 5432)            |       | (Claude, Gemini, etc.)|                 |
    |   +------------------------+       +--------------------+                   |
    +-----------------------------------------------------------------------------+
```

### Components
*   **FastAPI**: A high-performance Python web framework for building APIs with auto-generated OpenAPI documentation.
*   **PostgreSQL**: A robust, ACID-compliant relational database for storing assets, inventory levels, and maintenance logs.
*   **SQLAlchemy & Pydantic**: SQLAlchemy handles Object-Relational Mapping (ORM) to interface with Postgres, while Pydantic manages request validation and serialization.
*   **GenAI Context Extractor**: An integrated LLM agentic pipeline that parses messy technician reports into structured data.
*   **Docker & Docker Compose**: Simplifies local development and production deployments by orchestrating the app and database services in isolated network containers.

---

## 2. Setup and Installation

### Prerequisites
*   [Docker](https://www.docker.com/) (including Docker Compose)
*   Python 3.11+ (if running locally without Docker)

### Environment Configuration
Create a `.env` file in the root directory:
```env
# Database Settings
DATABASE_URL=postgresql://deepblue_user:deepblue_pass@db:5432/deepblue_db

# AI Service Settings
OPENAI_API_KEY=your-api-key-here
LLM_SERVICE_URL=https://api.openai.com/v1/chat/completions
```

### Building and Running the Application

#### Option A: Running via Docker Compose (Recommended)
Spin up the service stack (app + database) with:
```bash
docker compose up --build
```
This will automatically:
1. Build the FastAPI Docker image.
2. Pull and start a PostgreSQL container.
3. Apply database migrations and expose the app at `http://localhost:8001`.
   * **Visual Dashboard:** `http://localhost:8001/dashboard`
   * **API Docs (Swagger):** `http://localhost:8001/docs`

#### Option B: Running Locally (Standalone)
To run the server directly on your host machine:
1. Initialize virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the local server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   *(Note: Ensure you have a running PostgreSQL instance matching your `DATABASE_URL` in `.env`.)*
   This exposes:
   * **Visual Dashboard:** `http://localhost:8000/dashboard`
   * **API Docs (Swagger):** `http://localhost:8000/docs`

---

## 3. Core API Endpoints

### 3.1. Assets (`/api/v1/assets`)
Represents marine assets (e.g., Propulsion Thrusters, Drilling Platforms, Main Generators).
*   `GET /api/v1/assets` - List all tracked assets.
*   `POST /api/v1/assets` - Create a new asset.
*   `GET /api/v1/assets/{id}` - Get detailed asset information and current health status.
*   `PUT /api/v1/assets/{id}` - Update asset details.
*   `DELETE /api/v1/assets/{id}` - Remove an asset.

### 3.2. Inventory (`/api/v1/inventory`)
Tracks critical spare parts and supply chain availability (e.g., Gaskets, Valves, Bearings).
*   `GET /api/v1/inventory` - Retrieve current inventory list and stock levels.
*   `POST /api/v1/inventory` - Add a new spare part.
*   `GET /api/v1/inventory/{id}` - View stock levels and storage location.
*   `PUT /api/v1/inventory/{id}` - Adjust quantities or details.

### 3.3. Maintenance Reports (`/api/v1/maintenance`)
Logs of preventative and corrective maintenance.
*   `GET /api/v1/maintenance` - Retrieve maintenance report history.
*   `POST /api/v1/maintenance` - Create a new maintenance report manually.
*   `GET /api/v1/maintenance/{id}` - View specific report details.

### 3.4. GenAI Context Extraction (`/api/v1/extract`)
A post-endpoint designed to take unstructured text fields from field technicians and extract structured relational context.
*   `POST /api/v1/extract`
    *   **Request Body**:
        ```json
        {
          "field_notes": "Main engine turbocharger housing showing minor cracking near the oil return line. Noticed slight exhaust gas leak. Need to replace the O-ring seal (Part #OR-992-G) and inspect mounting brackets. Recommend immediate swap out during the next port call."
        }
        ```
    *   **Response Body**:
        ```json
        {
          "success": true,
          "extracted_data": {
            "asset_name": "Main Engine Turbocharger",
            "condition": "Cracked",
            "recommended_action": "Replace O-ring seal and inspect brackets",
            "urgency": "High",
            "parts_identified": [
              {
                "part_name": "O-ring seal",
                "part_number": "OR-992-G",
                "quantity": 1
              }
            ]
          }
        }
        ```

### 3.5. Visual Dashboard (`/dashboard`)
A premium, interactive web interface served directly from the FastAPI backend. It allows technicians to submit field notes, track extraction task status in real time, and view tracked assets, inventory stock counts, and maintenance logs.
*   `GET /dashboard` - Opens the visual single-page application.

---

## 4. Database Migrations & Testing

### Database Migrations (Alembic)
Database schemas are managed using Alembic. Migrations are executed automatically inside Docker Compose on startup via `alembic upgrade head`.

To run migrations manually:
*   **Apply all pending migrations**:
    ```bash
    alembic upgrade head
    ```
*   **Generate a new migration script**:
    Ensure database connectivity is active, then execute:
    ```bash
    alembic revision --autogenerate -m "Describe your schema changes"
    ```
*   **Rollback the last migration**:
    ```bash
    alembic downgrade -1
    ```

### Running the Test Suite (Pytest)
Our testing suite is built using `pytest`, `pytest-asyncio`, and `httpx` to verify REST endpoints, database layers, and asynchronous AI extraction tasks.

To run the test suite:
1. Initialize the dependencies locally:
   ```bash
   pip install -r requirements.txt
   ```
2. Execute the test suite runner:
   ```bash
   pytest -v
   ```
