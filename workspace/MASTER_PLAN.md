I will generate the `MASTER_PLAN.md` content directly here, as I currently lack the permissions to write files to the disk.

Here is the comprehensive **Master Implementation Plan**:

```markdown
# MASTER IMPLEMENTATION PLAN

## Architecture Overview

The system is designed as a modular **FastAPI** application. It serves as a personal exchange rate monitor, integrating with the Coinbase API for real-time data and providing a caching layer to respect rate limits.

### Core Components
1.  **API Layer (`app.py`)**: Handles HTTP requests, input validation, and route dispatching.
2.  **Service/Logic Layer**:
    *   **Coinbase Adapter (`api/coinbase_api.py`)**: Manages communication with the external Coinbase API.
    *   **Currency Logic (`core/currencies.py`)**: Manages supported currencies and response formatting.
    *   **Analytics (`core/analytics.py`)**: Handles complex calculations like the "Max Profit" algorithm.
    *   **Notifications (`core/notifications.py`)**: Manages email alerts based on rate thresholds.
3.  **Data Layer (`core/storage.py`)**: An abstraction over a persistent storage engine (SQLite) to handle:
    *   Caching latest rates (1-hour freshness).
    *   Storing historical data from webhooks.
    *   Querying data for graphing.

### Data Flow
*   **Read (Rates)**: Client -> API -> Check Cache/Storage -> (If Stale) Coinbase API -> Update Cache -> Response.
*   **Write (Webhook)**: External Provider -> Webhook Endpoint -> Validate -> Write to Storage -> Check Triggers (Notifications).
*   **Analytics**: Client -> API -> Query Storage -> Compute -> Response.

## Dependencies & Configuration

### System Requirements
*   Python 3.10+
*   SQLite3 (Standard Library)

### Python Dependencies (`requirements.txt`)
*   `fastapi`: Web framework.
*   `uvicorn`: ASGI server.
*   `requests`: HTTP client for external APIs.
*   *(New)* `pytest`: For robust testing (replacing/augmenting `unittest`).

### Configuration
Configuration should be managed via environment variables (or a `.env` file), including:
*   `COINBASE_API_URL`: Base URL for Coinbase (default provided).
*   `EMAIL_SMTP_SERVER`: (Mock/Real) SMTP settings for notifications.
*   `RATE_LIMIT_SECONDS`: Public API rate limit window (default: 60).

## Build Steps

1.  **Environment Setup**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Database Initialization**:
    *   The application will automatically initialize the SQLite database file (`rates.db`) and necessary tables on startup if they do not exist.

3.  **Execution**:
    ```bash
    uvicorn app:app --reload
    ```

## Versioning Strategy

*   **Semantic Versioning**: The project will follow `MAJOR.MINOR.PATCH`.
*   **Git Workflow**:
    *   `main`: Stable, production-ready code.
    *   `feature/*`: Feature-specific branches.
    *   Pull Requests required for merging into `main`.

## Testing Protocols

*   **Framework**: `unittest` (currently used) or `pytest`.
*   **Unit Tests**: Focus on isolated logic (e.g., `max_profit_exchange_times`, `Currencies` parsing).
*   **Integration Tests**:
    *   Mocking `requests.get` to test `CoinbaseAPI` without hitting external limits.
    *   Using an in-memory SQLite DB for testing storage interactions.
    *   `TestClient` from FastAPI for endpoint testing.
*   **CI/CD**: Tests must pass before merging PRs.

## Deployment & Rollback Procedures

### Deployment
1.  Pull latest code from `main`.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Restart `uvicorn` process.
4.  Database migrations (if schema changes) are handled largely by the app logic for this scale, or manual SQL scripts if strictly necessary.

### Rollback
1.  Revert to the previous git commit hash.
2.  If database schema changes were destructive, restore `rates.db` from backup (setup scheduled backups).
3.  Restart the service.

---

## Implementation Roadmap (Tasks)

The following tasks are derived from the project requirements and will be executed sequentially.

### 1. Implement Persistent Storage Layer
**Goal**: Create a storage abstraction using SQLite to persist exchange rates with timestamps.
*   **Input**: `core/currencies.py`
*   **Output**: `core/storage.py`
*   **Details**: Create `Storage` class with methods `save_rates`, `get_latest_rates`, `get_rates_in_range`.

### 2. Refactor Coinbase API for Caching
**Goal**: Modify `CoinbaseAPI` to respect rate limits (1 request/hour) using the storage layer.
*   **Input**: `api/coinbase_api.py`, `core/storage.py`
*   **Output**: Modified `api/coinbase_api.py`
*   **Details**: Check `get_latest_rates` freshness. If < 1 hour old, return cached. Else, fetch & save.

### 3. Implement Webhook Endpoint
**Goal**: Ingest real-time updates via `POST /webhook`.
*   **Input**: `app.py`, `core/storage.py`
*   **Output**: Modified `app.py`
*   **Details**: Parse payload, validate, and call `storage.save_rates`.

### 4. Implement Graphing API
**Goal**: Serve historical data via `GET /rates` with time range parameters.
*   **Input**: `app.py`, `core/storage.py`, `core/request_validation.py`
*   **Output**: Modified `app.py`, `core/request_validation.py`
*   **Details**: Handle `start` and `end` params. Query `storage.get_rates_in_range`.

### 5. Implement Email Notifications
**Goal**: Send alerts when USD -> BTC rate crosses threshold.
*   **Input**: `app.py`, `api/coinbase_api.py`, `core/storage.py`
*   **Output**: `core/notifications.py`, Modified `app.py`
*   **Details**: Trigger check on both Webhook ingestion and Coinbase fetch.

### 6. Implement Max Profit Algorithm
**Goal**: Calculate optimal trade times.
*   **Input**: `core/currencies.py`
*   **Output**: `core/analytics.py`
*   **Details**: Implement O(N) or O(N log N) algorithm to find max profit interval.

### 7. Implement Public API Rate Limiting
**Goal**: Limit clients to 1 request per 60 seconds.
*   **Input**: `app.py`
*   **Output**: `core/rate_limit.py`, Modified `app.py`
*   **Details**: Simple in-memory or storage-backed middleware to track client IPs and timestamps.
```