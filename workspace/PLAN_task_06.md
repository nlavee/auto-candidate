Here is the detailed **Task Specification** for implementing the Max Profit algorithm.

```markdown
# TASK SPECIFICATION: Implement Max Profit Algorithm

## 1. Objectives
Implement the `max_profit_exchange_times` function in a new module. This function determines the optimal entry (buy) and exit (sell) points for a single trade of a target currency against a purchasing currency (Base) to maximize profit, based on historical exchange rate data.

## 2. Input/Output Contracts

### Function Signature
**File:** `core/analytics.py`
```python
def max_profit_exchange_times(purchasing_currency: str, target_currency: str) -> list:
    pass
```

### Input
*   `purchasing_currency` (str): The currency held initially (e.g., "USD").
*   `target_currency` (str): The currency to trade (e.g., "BTC").

### Output
*   Returns a `list` containing four elements representing the optimal trade window:
    ```python
    [buy_timestamp, buy_rate_str, sell_timestamp, sell_rate_str]
    ```
    *   `buy_timestamp` (int): Unix timestamp (ms) of the purchase.
    *   `buy_rate_str` (str): The rate at purchase (amount of `target_currency` per 1 `purchasing_currency`).
    *   `sell_timestamp` (int): Unix timestamp (ms) of the sale.
    *   `sell_rate_str` (str): The rate at sale (amount of `target_currency` per 1 `purchasing_currency`).
*   **Constraint:** `sell_timestamp` must be strictly greater than `buy_timestamp`.
*   **Empty Case:** If no profitable trade is possible (or insufficient data), return `[]`.

## 3. Implementation Details

### A. Module Setup
*   Create a new file `core/analytics.py`.
*   Import `decimal` or use `float` carefully for comparisons, but ensure the output strings match the source data exactly.

### B. Data Access (Stub)
*   Since the persistent storage layer (`core/storage.py`) is not currently available/visible in this context, you must **implement a data stub** within `core/analytics.py`.
*   Create a helper function `_get_historical_rates(base_currency, target_currency)` that returns a list of dictionaries sorted by timestamp.
*   **Task Requirement:** Populate this stub with the data points from the **README.md** example to ensure the primary test case passes.
    *   Sample Data Structure: `{'timestamp': 1659390245000, 'rate': "0.000021"}`.

### C. Algorithm Logic
The goal is to maximize the ratio: `Rate(Buy) / Rate(Sell)`.
*   **Why?**
    *   Buying `1 Base` gets you `Rate(Buy)` amount of Target.
    *   Selling `Rate(Buy)` amount of Target gets you `Rate(Buy) * (1 / Rate(Sell))` amount of Base.
    *   Profit = `Rate(Buy) / Rate(Sell)`.
*   **Steps**:
    1.  Fetch sorted historical rates.
    2.  Iterate through the list while maintaining a record of the **maximum rate seen so far** (`max_buy_rate`).
    3.  For each step (potential **Sell** point), calculate the potential profit ratio using the `max_buy_rate` (best **Buy** point in the past) and the current rate.
    4.  Track the global maximum profit ratio and the associated timestamps.
    5.  Update `max_buy_rate` if the current rate is higher than what was seen previously (finding a better potential entry point for future sells).

### D. Edge Cases
*   **Strictly Increasing Rates:** If `Rate(t)` is strictly increasing over time, `Rate(Buy) < Rate(Sell)` for all `t_buy < t_sell`. The ratio is always < 1 (Loss). Return `[]`.
*   **Insufficient Data:** If fewer than 2 data points exist, return `[]`.

## 4. Verification Steps

### Automated Tests
Create `tests/test_analytics.py` and implement the following test cases:

1.  **Happy Path (README Example)**
    *   **Input**: Mock `_get_historical_rates` to return:
        *   `t=1659390245000, r="0.000021"`
        *   `t=1659500000000, r="0.000010"`
        *   `t=1659695606000, r="0.000005"`
    *   **Expected Output**: `[1659390245000, "0.000021", 1659695606000, "0.000005"]`

2.  **No Profit Possible**
    *   **Input**: Rates increasing: `[(t1, "0.1"), (t2, "0.2"), (t3, "0.3")]`.
    *   **Expected Output**: `[]`.

3.  **Local Maxima**
    *   Ensure the algorithm finds the *global* maximum, not just the first profitable pair.
    *   **Input**: `[(t1, "10"), (t2, "5"), (t3, "20"), (t4, "2")]`.
        *   Trade A: Buy 10, Sell 5 -> 2x.
        *   Trade B: Buy 20, Sell 2 -> 10x.
    *   **Expected Output**: Buy at `t3` ("20"), Sell at `t4` ("2").
```