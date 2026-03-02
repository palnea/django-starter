# Testing

## Test Data with model_bakery

This project uses [model_bakery](https://model-bakery.readthedocs.io/) to generate test data. Always use the correct import:

```python
from model_bakery import baker

# Create a single instance
user = baker.make("user.User")

# Create with specific fields
user = baker.make("user.User", email="test@example.com")

# Create multiple instances
users = baker.make("user.User", _quantity=3)
```

For shared or complex fixtures, add recipes to `custom_test/baker_recipes.py`:

```python
from model_bakery.recipe import Recipe

my_recipe = Recipe("myapp.MyModel", name="default-name")
```

See `CLAUDE.md` for the full testing guide, including base classes, helpers, and permission testing.
