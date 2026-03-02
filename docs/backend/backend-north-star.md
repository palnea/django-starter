# Backend North Star

Guiding principles and performance patterns for the Django backend.

## N+1 Query Prevention

N+1 queries are one of the most common performance pitfalls in Django. They occur when code iterates over a queryset and triggers an additional database query for each row (e.g., accessing a ForeignKey or ManyToMany relation inside a loop).

### Rules

1. **Every queryset that touches a relation must use `select_related` or `prefetch_related`.**
2. Use `select_related` for ForeignKey and OneToOneField (SQL JOIN, single query).
3. Use `prefetch_related` for ManyToManyField and reverse ForeignKey relations (separate query, joined in Python).
4. Define a `get_queryset` override on viewsets rather than relying on the default `objects.all()`.
5. Review queries in tests using `self.assertNumQueries()` for critical list endpoints.

### Examples

#### select_related (ForeignKey / OneToOne)

```python
# Bad - N+1: one query per subscription to fetch the user
for sub in Subscription.objects.all():
    print(sub.user.email)

# Good - single JOIN query
for sub in Subscription.objects.select_related("user").all():
    print(sub.user.email)
```

#### prefetch_related (ManyToMany / reverse FK)

```python
# Bad - N+1: one query per user to fetch their payments
for user in User.objects.all():
    print(user.payment_set.all())

# Good - two queries total (one for users, one for payments)
for user in User.objects.prefetch_related("payment_set").all():
    print(user.payment_set.all())
```

#### ViewSet pattern

```python
class SubscriptionViewSet(OwnershipMixin, ModelViewSet):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return (
            Subscription.objects
            .select_related("user", "plan")
            .prefetch_related("features")
        )
```

#### Nested prefetches with Prefetch objects

```python
from django.db.models import Prefetch

User.objects.prefetch_related(
    Prefetch(
        "payment_set",
        queryset=Payment.objects.select_related("subscription").order_by("-created_at"),
    )
)
```

### Verifying in Tests

```python
def test_list__no_n_plus_one(self):
    """List endpoint executes a constant number of queries."""
    baker.make(MyModel, _quantity=5)
    self.authenticate_as(self.admin)
    # Adjust the expected count to match your endpoint
    with self.assertNumQueries(2):
        self.client.get(reverse("mymodel-list"))
```
