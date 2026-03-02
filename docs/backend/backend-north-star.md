# Backend North Star

Long-term architectural direction and trade-off records for the Django backend.

---

### Dependency Injection in Services

#### Current pattern: `@staticmethod`

All service methods are declared as `@staticmethod` on plain classes:

```python
class UserService:
    @staticmethod
    def deactivate(user_id: str) -> User:
        user = User.objects.get(id=user_id)
        ...
```

**Advantages:**

- Zero boilerplate -- no constructor, no wiring, no DI container.
- Easy to call from views: `UserService.deactivate(user_id)`.
- Familiar to every Django developer; matches the "fat models, thin views,
  service layer" convention.

**Trade-offs:**

- Hard dependencies on ORM (`User.objects`) are embedded inside method bodies.
  This makes unit-testing with fakes difficult without `unittest.mock.patch`.
- Replacing a collaborator (e.g., swapping a payment gateway) requires either
  monkey-patching or adding conditional logic.
- Static methods cannot be overridden through inheritance in a meaningful way,
  limiting extension points.

#### Allowed pattern: default-argument injection

When a service method needs to be testable without `mock.patch`, use a
**default-argument** to inject the dependency:

```python
class PaymentService:
    @staticmethod
    def charge(
        user_id: str,
        amount: Money,
        gateway: PaymentGateway = None,
    ) -> Payment:
        if gateway is None:
            gateway = StripeGateway()  # production default
        return gateway.charge(user_id, amount)
```

This preserves the static-method convention while allowing tests to pass a
fake:

```python
def test_charge__insufficient_funds(self):
    fake_gw = FakeGateway(decline=True)
    with self.assertRaises(CustomException):
        PaymentService.charge(user.id, Money(100, "USD"), gateway=fake_gw)
```

**Rules for this pattern:**

1. The default value must be `None`, with the production implementation
   instantiated inside the method body. This avoids mutable default-argument
   pitfalls and keeps the import at runtime only.
2. Only use this for **external boundaries** (payment gateways, email senders,
   third-party API clients). Do not inject the Django ORM -- use
   `mock.patch` or factory-boy fixtures for model-layer testing.
3. Document the injectable parameter in the method's docstring so callers know
   it exists.

#### What we are NOT adopting

- **Constructor-based DI with a container** (e.g., `dependency-injector`,
  `injector`). The added indirection and learning curve is not justified for
  the current team and codebase size.
- **Instance methods on services.** Keeping services as static-method bags
  avoids accidental shared state between requests.

#### When to revisit

Re-evaluate this decision if:

- The number of external integrations exceeds five and mocking becomes a
  maintenance burden.
- The team adopts a hexagonal / ports-and-adapters architecture where
  interface segregation becomes critical.
- A new team member proposes a concrete DI spike with measurable test-speed
  or readability improvements.
