# Tooling, Scripts, and CI

## poetry.lock Commit Policy

> **WARNING: `poetry.lock` is git-ignored in this repository.**
>
> The `.gitignore` file explicitly excludes `poetry.lock`. This means every
> developer (and CI) runs `poetry install` against the *ranges* declared in
> `pyproject.toml` rather than a pinned lock file.

### Why this matters

| Scenario | With committed lock file | Without committed lock file (current) |
|---|---|---|
| Reproducible builds | Exact same versions everywhere | Versions may differ across machines and CI runs |
| Dependency drift | Only changes when someone runs `poetry update` | Every `poetry install` may resolve differently |
| CI failures | Deterministic | A new transitive dependency release can break CI without any code change |

### Current trade-off

The project treats `poetry.lock` similarly to a library (not an application), so
the lock file is excluded. This is a deliberate choice noted in the `.gitignore`
comments:

```gitignore
# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock
#   in version control. This is especially recommended for binary packages to
#   ensure reproducibility, and is more commonly ignored for libraries.
poetry.lock
```

### Recommendation for production applications

If the project is deployed as an application (which it is -- Django + Gunicorn),
the Poetry documentation recommends committing `poetry.lock` to ensure
reproducible deployments. To adopt this:

1. Remove the `poetry.lock` line from `.gitignore`.
2. Run `poetry lock` to generate the lock file.
3. Commit `poetry.lock`.
4. Update CI to run `poetry install --no-update` (installs from the lock file
   without re-resolving).

Until this change is made, be aware that CI and production environments may
resolve different dependency versions than your local machine.
