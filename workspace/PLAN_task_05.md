To facilitate the implementation of **Task 5 (Email Notifications)**, I have prepared the detailed **Task Specification**.

This plan focuses on creating the notification logic and integrating it into the existing application flow. It addresses the requirement to trigger notifications from both the Coinbase API fetch and the Webhook ingestion, necessitating a partial implementation of the Webhook endpoint if it does not yet exist.

```markdown
# TASK SPECIFICATION: Implement Email Notifications

## 1. Objectives
-   **Create Notification Logic**: Implement a service to check if the USD to BTC exchange rate exceeds the defined threshold (`0.000045 BTC` per `1 USD`).
-   **Email Alerting**: Send an email using a mock function when the condition is met.
-   **Integration**: Hook this logic into:
    1.  The `CoinbaseAPI` data fetching process.
    2.  The `POST /webhook` endpoint (to be scaffolded if missing).

## 2. Input/Output Contracts

### `core/notifications.py` (New)
*   **Class**: `NotificationService`
*   **Method**: `check_and_notify(rates_data: dict)`
    *   **Input**: A dictionary representing the rates (standardized format favored by the app, e.g., `{"USD": {"BTC": "0.00005"}}`).
    *   **Logic**:
        1.  Extract the `USD` -> `BTC` rate.
        2.  Parse as float.
        3.  If `rate > 0.000045`, call `send_email`.
    *   **Output**: `True` if notification sent, `False` otherwise (or `void`).
*   **Helper**: `send_email(recipient, subject, body)` (Mock implementation provided in requirements).

### `app.py` (Update)
*   **Endpoint**: `POST /webhook`
    *   **Input**: JSON Payload (Coinbase style rate change).
    *   **Behavior**: Parse payload, extract rates, delegate to `NotificationService`.
    *   **Output**: `200 OK`.

## 3. Detailed Implementation Steps

### Step 1: Create `core/notifications.py`
1.  Define `send_email(recipient, subject, body)`:
    *   Print the email details to `stdout` for verification (e.g., `[EMAIL SENT] To: ... Subject: ...`).
2.  Define `NotificationService` class.
3.  Implement `check_and_notify(self, data)`:
    *   Traverse `data` to find the BTC rate relative to USD.
    *   Handle cases where the structure might be `{ "currency": "USD", "rates": { "BTC": ... } }` (API response) or `{ "USD": { "BTC": ... } }` (Internal format). *Note: Standardizing on the internal format `{Base: {Target: Rate}}` is recommended before calling this service.*
    *   Threshold: `0.000045`.
    *   If condition met:
        *   Subject: "Favorable BTC Rate Detected"
        *   Body: "You can now purchase {rate} BTC with 1 USD."
        *   Recipient: "user@example.com" (Hardcoded for now).

### Step 2: Update `api/coinbase_api.py`
1.  Import `NotificationService`.
2.  Instantiate the service in `__init__`.
3.  Modify `getExchangeRate`:
    *   Capture the `parsedExchangedRate` (which is in format `{Base: {Target: Rate}}`).
    *   Pass this data to `notification_service.check_and_notify(parsedExchangedRate)`.
    *   **Note**: Ensure this happens *before* returning the response.

### Step 3: Update `app.py`
1.  Import `NotificationService`.
2.  Instantiate `notification_service`.
3.  Define/Update `POST /webhook` endpoint:
    *   **Context**: If the webhook task (Task 3) was not fully completed, implement the basic structure to receive the JSON payload.
    *   Extract `data.rates` and `data.base_currency`.
    *   Format into the internal structure: `{base_currency: rates_dict}`.
    *   Call `notification_service.check_and_notify(...)`.
    *   Return `{"status": "processed"}`.

## 4. Verification Steps

### Automated Tests
*   **`tests/test_notifications.py`** (New File):
    *   **Test 1 (Threshold Met)**: Pass data with USD->BTC = `0.000050`. Assert `send_email` is called (mocking `send_email` or capturing stdout).
    *   **Test 2 (Threshold Not Met)**: Pass data with USD->BTC = `0.000040`. Assert `send_email` is NOT called.
    *   **Test 3 (Missing Data)**: Pass data without USD or BTC. Assert no error/no email.

### Manual Verification
1.  **Run Application**: `uvicorn app:app --reload`
2.  **Trigger via API**:
    *   Make a request to `GET /rates?base=fiat`.
    *   *Note*: Since live Coinbase rates vary, you might temporarily lower the threshold in code to `0.00000001` to force a trigger, or mock the API response.
    *   Observe console for `[EMAIL SENT]`.
3.  **Trigger via Webhook**:
    *   Send a curl command:
        ```bash
        curl -X POST http://127.0.0.1:8000/webhook \
        -H "Content-Type: application/json" \
        -d '{"type": "rate_change", "data": {"base_currency": "USD", "rates": {"BTC": "0.000050"}}}'
        ```
    *   Observe console for `[EMAIL SENT]`.
```