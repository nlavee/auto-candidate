I am currently unable to write files to the disk as the `write_file` and `run_shell_command` tools are not available in my current environment.

However, I have prepared the detailed **Task Specification** (`TASK_PLAN.md`) below, which defines the implementation strategy for the Graphing API.

***

# TASK_PLAN.md

```markdown
# Task 4: Implement Graphing API - Implementation Plan

## Context
The goal is to enable historical data visualization by extending the `GET /rates` endpoint. This requires handling new query parameters (`base_currency`, `target_currency`, `start`, `end`) and retrieving data from a persistent storage layer.

## Pre-requisites
- **Storage Layer**: The `core/storage.py` file appears to be missing from the current file tree despite being listed as a dependency. **I will implement a lightweight SQLite-backed storage layer** as part of this task to ensure the graphing API handles data retrieval correctly.

## Proposed Changes

### 1. Core Storage (`core/storage.py`)
- **Action**: Create this file.
- **Responsibility**: Handle SQLite database connections and queries.
- **Key Methods**:
  - `__init__`: Initialize `rates.db` with a table `exchange_rates` if it doesn't exist.
    - Schema: `id` (PK), `timestamp` (Integer), `base_currency` (Text), `target_currency` (Text), `rate` (Real).
  - `get_rates(base_currency, target_currency, start_timestamp, end_timestamp)`: 
    - Query: `SELECT timestamp, rate FROM exchange_rates WHERE base_currency=? AND target_currency=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC`.
    - Return: A list of dictionaries: `[{'timestamp': <int>, 'value': <str>}, ...]`.
  - `save_rate(timestamp, base_currency, target_currency, rate)`: 
    - Helper method to insert data (essential for testing/seeding).

### 2. Request Validation (`core/request_validation.py`)
- **Action**: Refactor `validate_rates_request` to support dual modes.
- **Logic**:
  - **Mode A (Current)**: If `base` query param is present.
    - Keep existing validation (values: 'fiat', 'token').
    - Return: `{"mode": "current", "params": {"base": "..."}}`.
  - **Mode B (Graphing)**: If `base_currency` AND `target_currency` AND `start` are present.
    - **Validation**:
      - `base_currency`, `target_currency`: Non-empty strings.
      - `start`: Integer (Unix timestamp in ms).
      - `end`: Optional Integer (Unix timestamp in ms). Defaults to current time if missing.
    - Return: `{"mode": "history", "params": {"base_currency": ..., "target_currency": ..., "start": ..., "end": ...}}`.
  - **Error Handling**: Raise `400 Bad Request` if parameters do not match either mode or are malformed.

### 3. API Endpoint (`app.py`)
- **Action**: Update `get_rates` handler.
- **Logic**:
  - Call `validate_rates_request`.
  - Check `validated['mode']`:
    - **If 'current'**:
      - Call `coinbase_api.getExchangeRate(validated['params'])` (Existing Logic).
    - **If 'history'**:
      - Instantiate `Storage`.
      - Call `storage.get_rates(...)`.
      - Construct response: `{"results": rates_list}`.
      - Handle empty results gracefully (return empty list).

## Verification Plan

### Automated Tests
- **`tests/test_storage.py`**:
  - Verify database file creation.
  - Test `save_rate` and `get_rates` for correct filtering by time range and currency pair.
- **`tests/test_request_validation.py`**:
  - Test valid inputs for both "current" and "graphing" modes.
  - Test invalid inputs (e.g., missing `start`, non-integer `start`).
- **`tests/test_app_integration.py`**:
  - Mock `CoinbaseAPI` and `Storage`.
  - Verify correct routing logic in `app.py` based on parameters.

### Manual Verification
1.  **Seed Data**: Since the ingestion tasks are separate, I will manually inject a few rows into `rates.db` using a temporary script or python shell.
2.  **Request**: 
    ```bash
    curl "http://localhost:8000/rates?base_currency=USD&target_currency=BTC&start=1660000000000"
    ```
3.  **Expectation**: Receive a JSON response with the seeded data points.
```