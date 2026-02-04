The `write_file` tool is not currently available in my toolset. I will output the content of `TASK_PLAN.md` below.

```markdown
# Task Plan: Implement Webhook Endpoint

## Status
- **Task ID**: `task_03`
- **Title**: Implement Webhook Endpoint
- **Dependencies**: `task_01` (Persistent Storage Layer)
- **Target Files**: `app.py`, `core/schemas.py` (new)

## Objectives
1.  Create a `POST /webhook` endpoint in `app.py` to ingest real-time exchange rate updates from an external provider.
2.  Validate the incoming webhook payload to ensure it matches the expected structure (specifically `type="rate_change"`).
3.  Persist the received rate data using the `core/storage.py` abstraction (from Task 1).

## Implementation Steps

### 1. Define Data Models
Create a new file `core/schemas.py` (or add to `app.py` if minimal) to define Pydantic models for the webhook payload. This ensures strict validation.

*   **Model**: `WebhookRates` (Mapping of currency codes to values)
*   **Model**: `WebhookData`
    *   `base_currency`: str
    *   `published_at`: int (Unix timestamp)
    *   `rates`: Dict[str, str]
*   **Model**: `WebhookPayload`
    *   `type`: str (Must be "rate_change")
    *   `data`: `WebhookData`

### 2. Implement Storage Integration
*   Import `Storage` from `core.storage` (Assumed to exist from `task_01`).
*   Ensure `Storage` has a method `save_rates(base_currency: str, rates: dict, timestamp: int)`.
*   *Note*: If `core/storage.py` is missing in the current environment (due to task sequence), scaffold a basic version or stub to ensure the webhook code is testable.

### 3. Update `app.py`
*   Import the Pydantic models.
*   Initialize the `Storage` instance.
*   Add the endpoint:
    ```python
    @app.post("/webhook")
    async def receive_webhook(payload: WebhookPayload):
        # Validate 'type'
        if payload.type != "rate_change":
            # Log warning, return 400 or ignore
            pass
            
        # Extract data
        base = payload.data.base_currency
        timestamp = payload.data.published_at
        rates = payload.data.rates
        
        # Save to storage
        storage.save_rates(base_currency=base, rates=rates, timestamp=timestamp)
        
        return {"status": "success"}
    ```

### 4. Verification & Testing
*   **Manual Verification**: Use `curl` to send a valid POST request to `/webhook`.
*   **Unit Tests**:
    *   Test with valid payload: Ensure 200 OK and storage is called.
    *   Test with invalid `type`: Ensure appropriate error or ignore.
    *   Test with malformed JSON: Ensure 422 Unprocessable Entity (FastAPI default).

## User Review Required
> [!NOTE]
> `core/storage.py` is listed as a dependency but does not appear in the provided file listing. The implementation will rely on the interface defined in the Master Plan (`save_rates`). If the file is missing, I will create a minimal implementation to satisfy the import.
```