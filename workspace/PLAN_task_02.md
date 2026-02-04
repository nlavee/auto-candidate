Based on the Master Plan and the current state of the repository (where `core/storage.py` is missing), here is the detailed **Task Specification** for Task 02.

```markdown
# TASK SPECIFICATION: Refactor Coinbase API for Caching

## 1. Objectives
The primary objective is to make the `CoinbaseAPI` compliant with the strict rate-limiting constraints (1 request per hour) by implementing a caching layer.
Since the dependency `core/storage.py` (Task 01) is currently missing from the codebase, **this task must also include the implementation of the persistent storage layer**.

**Key Goals:**
1.  Implement a `Storage` class in `core/storage.py` using `sqlite3`.
2.  Refactor `CoinbaseAPI` to check `Storage` for fresh data (< 1 hour old) before calling the external Coinbase API.
3.  Ensure new data fetched from Coinbase is immediately persisted to `Storage`.
4.  Maintain the existing input/output format of `/rates`.

## 2. Input/Output Contracts

### `core/storage.py` (New Component)
*   **Class**: `Storage`
*   **Method**: `save_rates(currency: str, rates: dict)`
    *   **Input**: Currency code (e.g., "USD"), dictionary of rates (e.g., `{"BTC": "...", "ETH": "..."}`).
    *   **Effect**: Inserts a record into the DB with the current UTC timestamp.
*   **Method**: `get_latest_rates(currency: str)`
    *   **Input**: Currency code.
    *   **Output**: A tuple/dict containing `(timestamp, rates_dict)` or `None` if not found.

### `api/coinbase_api.py` (Refactored)
*   **Method**: `getExchangeRate(validated_params)`
    *   **Input**: `{"param_name": "base", "param_value": "fiat" | "token"}`.
    *   **Output**: List of dictionaries (same as existing), e.g., `{"USD": {"BTC": ...}}`.
    *   **Behavior Change**:
        *   Calculates list of currencies to fetch based on `param_value`.
        *   For each currency:
            1.  Call `storage.get_latest_rates(currency)`.
            2.  If data exists AND `(current_time - timestamp) < 1 hour`: Use cached data.
            3.  Else: Call `makeApiCall`, save to storage, use fresh data.

## 3. Detailed Implementation Steps

### Step 1: Implement Storage Layer (`core/storage.py`)
Create a `Storage` class that handles SQLite interactions.
*   **Initialize**: In `__init__`, connect to `rates.db`. Create a table `exchange_rates` if it doesn't exist.
    *   Schema suggestion: `id (AUTOINCREMENT), currency (TEXT), rates (JSON/TEXT), timestamp (REAL/INTEGER)`.
*   **Save**: Implement `save_rates` to `INSERT` data.
*   **Retrieve**: Implement `get_latest_rates` to `SELECT` the most recent entry for a given currency.

### Step 2: Refactor `CoinbaseAPI` (`api/coinbase_api.py`)
*   Import `Storage` from `core.storage`.
*   Initialize `self.storage = Storage()` in `__init__`.
*   Modify `getExchangeRate`:
    *   Iterate through the required currencies (e.g., USD, EUR, SGD).
    *   **Check Cache**: Query `self.storage` for the currency.
    *   **Validation Logic**:
        *   If record exists: Check if `time.time() - record_timestamp < 3600`.
        *   If fresh: Add to results list without API call.
        *   If stale or missing: Perform `makeApiCall`, then call `self.storage.save_rates`, then add to results.
*   **Note**: Ensure the final return structure matches exactly what `Currencies.getInterestedCurrencies` expects (or refactor how that is called if you change the flow to build the response incrementally).
    *   *Current Flow*: `getCurrencyList` -> `generateApiRequest` -> `makeApiCall` -> `getInterestedCurrencies`.
    *   *New Flow*: You might need to construct the `response` object manually for cached items to mimic the structure `{ "data": { "currency": "...", "rates": ... } }` so `getInterestedCurrencies` can still process it, OR refactor `getInterestedCurrencies` to handle the simpler dict structure.
    *   *Recommendation*: Wrap cached data in the expected structure `{'data': {'currency': ..., 'rates': ...}}` to minimize changes to `core/currencies.py`.

### Step 3: Updates Tests
*   Create `tests/test_storage.py` to verify DB operations.
*   Update `tests/test_coinbase_api.py`:
    *   Mock `core.storage.Storage`.
    *   Test case: **Cache Hit** (Ensure `requests.get` is NOT called).
    *   Test case: **Cache Miss** (Ensure `requests.get` IS called and `storage.save_rates` is called).
    *   Test case: **Stale Cache** (Ensure `requests.get` IS called).

## 4. Verification Steps

### Automated Tests
Run the following commands:
```bash
# 1. Test the new storage layer
python3 -m unittest tests/test_storage.py

# 2. Test the API logic with mocking
python3 -m unittest tests/test_coinbase_api.py

# 3. Ensure existing logic didn't break
python3 -m unittest tests/test_currencies.py
```

### Manual Verification
1.  Start the server: `uvicorn app:app --reload`
2.  Make a request: `curl "http://127.0.0.1:8000/rates?base=fiat"`
3.  Check the server logs. You should see "Making API call..." (or similar).
4.  Immediately make the same request again.
5.  Check logs. You should **NOT** see "Making API call...". The response should be instant.
6.  Wait 1 hour (or manually modify the DB timestamp/reduce limit for testing) to verify it refreshes.
```