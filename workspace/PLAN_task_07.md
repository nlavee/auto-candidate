Here is the Task Specification for Task 7: Implement Public API Rate Limiting.

```markdown
# TASK SPECIFICATION: Implement Public API Rate Limiting

## 1. Objectives
-   Protect the application from abuse by limiting the frequency of requests from a single client.
-   Implement a strict limit of **1 request per 60 seconds** per client IP address.
-   Return a standard `429 Too Many Requests` HTTP status code when the limit is exceeded.

## 2. Input/Output Contracts

### New Component: `core/rate_limit.py`
*   **Class**: `RateLimiter`
*   **Method**: `check_rate_limit(client_id: str) -> bool`
    *   **Input**: `client_id` (string, e.g., IP address).
    *   **Output**:
        *   Raises `HTTPException(429)` if limit exceeded.
        *   Returns `None` (allows execution) if within limits.

### Modified Component: `app.py`
*   **Middleware/Dependency**: Integrate `RateLimiter` into the FastAPI request lifecycle.
*   **Behavior**:
    *   **Request 1 (t=0s)**: Returns `200 OK` (JSON response).
    *   **Request 2 (t=30s)**: Returns `429 Too Many Requests` with JSON body `{"detail": "Rate limit exceeded. Try again in X seconds."}`.
    *   **Request 3 (t=61s)**: Returns `200 OK`.

## 3. Detailed Implementation Steps

### Step 1: Create Rate Logic (`core/rate_limit.py`)
Create a simple in-memory rate limiter. Since the requirement is strict (1 req / 60s), we only need to store the *last* successful request timestamp for each client.

1.  Create `core/rate_limit.py`.
2.  Define a class `RateLimiter`.
    *   Initialize with a dictionary: `self.client_timestamps = {}`.
    *   Initialize with a constant: `RATE_LIMIT_DURATION = 60`.
3.  Implement `check_rate_limit(self, client_ip: str)`:
    *   Get `current_time`.
    *   Check if `client_ip` exists in `self.client_timestamps`.
    *   If exists:
        *   Calculate `elapsed = current_time - last_time`.
        *   If `elapsed < RATE_LIMIT_DURATION`:
            *   Raise `HTTPException(status_code=429, detail="Rate limit exceeded")`.
    *   Update `self.client_timestamps[client_ip] = current_time`.

### Step 2: Integrate into FastAPI (`app.py`)
Use a FastAPI **Dependency** to apply this logic easily to specific or all endpoints.

1.  Import `RateLimiter` from `core.rate_limit`.
2.  Import `Depends`, `Request` from `fastapi`.
3.  Instantiate the limiter globally: `limiter = RateLimiter()`.
4.  Create a dependency function `limit_requests(request: Request)`:
    *   Extract IP: `client_ip = request.client.host`.
    *   Call `limiter.check_rate_limit(client_ip)`.
5.  Apply the dependency to the `app` or specific routes.
    *   *Recommendation*: Apply globally to `app.get('/rates')` specifically, or globally via `app = FastAPI(dependencies=[Depends(limit_requests)])` if all endpoints should be protected. Given the context, protecting `/rates` is the priority.

    ```python
    @app.get('/rates', dependencies=[Depends(limit_requests)])
    def get_rates(request: Request):
        # ... existing logic ...
    ```

## 4. Verification Steps

### Automated Testing
Since we cannot easily mock time in a running server without complex setup, use `unittest` with mocking for the logic class.

1.  Create `tests/test_rate_limit.py`.
2.  Test `RateLimiter` logic:
    *   **Test Allow**: Call `check_rate_limit("1.2.3.4")` -> Should pass.
    *   **Test Block**: Call `check_rate_limit("1.2.3.4")` immediately again -> Should raise HTTPException 429.
    *   **Test Expiry**: Mock `time.time`, call, advance time by 61s, call again -> Should pass.

### Manual Verification
1.  Run the server: `uvicorn app:app --reload`.
2.  Make a request: `curl -v http://127.0.0.1:8000/rates?base=fiat`.
    *   Expect: `200 OK`.
3.  Immediately make the same request again.
    *   Expect: `429 Too Many Requests`.
4.  Wait 60 seconds.
5.  Make the request again.
    *   Expect: `200 OK`.
```