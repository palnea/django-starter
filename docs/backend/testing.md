# Testing

Guidelines and patterns for the Django test suite.

## Database Transaction Isolation in Tests

Django provides two test case classes that handle database state differently. Choosing the wrong one leads to flaky tests or silent data leaks between tests.

### TestCase (default choice)

`django.test.TestCase` wraps each test in a transaction and rolls it back at the end. This is fast because no data is actually written to disk.

```python
from custom_test.base_test import CustomAPITestCase  # extends TestCase

class OrderTests(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.authenticate_as(self.user)

    def test_create_order(self):
        """Order is created and rolled back after this test."""
        response = self.client.post(reverse("order-list"), {"item": "widget"})
        self.assertEqual(response.status_code, 201)
```

**Use `TestCase` (via `CustomAPITestCase`) when:**
- The code under test does not explicitly manage transactions.
- You do not need to test behaviour that depends on `on_commit` callbacks.
- You want maximum test speed.

### TransactionTestCase (when you need real commits)

`django.test.TransactionTestCase` lets each test actually commit to the database, then truncates tables between tests. It is significantly slower.

```python
from django.test import TransactionTestCase

class PaymentWebhookTests(TransactionTestCase):
    def test_webhook__idempotent_on_retry(self):
        """Webhook handler commits, so we need real transactions."""
        # First call commits the payment
        self.client.post("/webhooks/payment/", data=payload)
        # Retry should be idempotent
        self.client.post("/webhooks/payment/", data=payload)
        self.assertEqual(Payment.objects.count(), 1)
```

**Use `TransactionTestCase` when:**
- The code calls `transaction.on_commit()` and you need the callback to fire.
- You are testing code that uses `select_for_update()` or explicit `transaction.atomic()` blocks where rollback semantics matter.
- You need to test database-level constraints that only surface after a real commit (e.g., deferred unique constraints).

### Rules

1. **Default to `CustomAPITestCase`** (which extends `TestCase`). Only switch to `TransactionTestCase` when a test genuinely requires committed data.
2. **Never mix the two in a single test class.** A class inherits from one or the other.
3. **Be aware of `on_commit` in TestCase.** Django 4.2+ provides `self.captureOnCommitCallbacks(execute=True)` as a context manager to test `on_commit` hooks without switching to `TransactionTestCase`:
   ```python
   def test_sends_email_on_commit(self):
       with self.captureOnCommitCallbacks(execute=True) as callbacks:
           Order.objects.create(user=self.user, item="widget")
       self.assertEqual(len(mail.outbox), 1)
   ```
4. **Isolate slow transaction tests.** Put them in a separate test module (e.g., `test_transactions.py`) so the fast test suite can be run independently.
