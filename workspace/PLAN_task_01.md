To ensure the developer has a clear guide for implementing the storage layer, I have prepared the following task plan.

```markdown
# Task 01: Implement Persistent Storage Layer

## Objectives
- Create a robust storage mechanism using SQLite to persist exchange rate data.
- The storage layer must support high-precision timestamps (milliseconds) and accurate rate storage.
- Implement an abstraction layer (`Storage` class) to decouple the application from the specific database implementation, facilitating future changes or testing.
- Support the specific query patterns required by future tasks:
    - **Caching**: Retrieving the most recent snapshot of rates.
    - **Graphing**: Retrieving a time-series of a specific currency pair.

## Input/Output Contracts
- **Input Context**:
    - `core/currencies.py`: Defines the data structures (nested dictionaries) that will need to be flattened for storage and reconstructed for retrieval.
- **Target File**: `core/storage.py`
- **Test File**: `tests/test_storage.py`

## Detailed Implementation Steps

### 1. Define Database Schema
The SQLite database (`rates.db`) will contain a single table `exchange_rates` optimized for time-series data.

- **Table**: `exchange_rates`
    - `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
    - `timestamp`: `INTEGER` (Unix timestamp in milliseconds).
    - `base_currency`: `TEXT` (e.g., 'USD').
    - `target_currency`: `TEXT` (e.g., 'BTC').
    - `rate`: `REAL` (The exchange rate value).

- **Indices**:
    - Create an index on `timestamp` to optimize range queries (Task 4) and finding the latest entry.
    - Create a composite index on `(base_currency, target_currency)` for efficient filtering.

### 2. Implement `core/storage.py`
Create a class `Storage` with the following methods:

- **`__init__(self, db_path='rates.db')`**:
    - Establish a connection to the SQLite database.
    - Call `_initialize_db`.

- **`_initialize_db(self)`**:
    - Execute SQL to create the `exchange_rates` table and indices if they do not exist.

- **`save_rates(self, rates_data: dict, timestamp: int = None)`**:
    - **Input**: `rates_data` matches the format `{'USD': {'BTC': 0.001, ...}, ...}`. `timestamp` is optional (defaults to `current_time_millis`).
    - **Logic**: Flatten the nested dictionary into rows `(timestamp, base, target, rate)` and perform a bulk insert (`executemany`).

- **`get_latest_rates(self)`**:
    - **Purpose**: Used for Caching (Task 2) and current API responses.
    - **Logic**:
        1. Query the maximum `timestamp` from the table.
        2. Query all rows matching that timestamp.
        3. Reconstruct the nested dictionary format `{'Base': {'Target': rate}}`.
    - **Returns**: A tuple `(timestamp, data_dict)`. Returns `(None, {})` if empty.

- **`get_rates_in_range(self, base_currency: str, target_currency: str, start: int, end: int = None)`**:
    - **Purpose**: Used for Graphing (Task 4).
    - **Logic**:
        - Select `timestamp` and `rate` where `base` and `target` match, and `timestamp` is between `start` and `end` (or now).
        - Order by `timestamp ASC`.
    - **Returns**: A list of dicts: `[{'timestamp': 123..., 'value': 0.001}, ...]`.

### 3. Implement Verification Tests (`tests/test_storage.py`)
Create a `unittest` suite using an in-memory database (`:memory:`) to ensure isolation.

- **`test_initialization`**: Verify the table and indices are created.
- **`test_save_and_retrieve_latest`**:
    - Save a dataset.
    - Call `get_latest_rates` and assert the returned structure and values match.
- **`test_get_rates_in_range`**:
    - Save multiple datasets at different timestamps (`t1`, `t2`, `t3`).
    - Call `get_rates_in_range` with a window covering only `t2`.
    - Verify only the `t2` record is returned.
- **`test_empty_db`**: Ensure `get_latest_rates` handles an empty database without crashing.

## Verification Steps
1.  Run the newly created tests:
    ```bash
    python3 -m unittest tests/test_storage.py
    ```
2.  Ensure all tests pass.
3.  (Optional) Manually instantiate `Storage` in a python shell to verify `rates.db` creation on disk.
```