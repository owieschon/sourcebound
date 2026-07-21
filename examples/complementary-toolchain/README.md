# Complementary toolchain fixture

This fixture gives each check one job. A source-bound table tracks the action registry, an editorial rule checks a wording constraint, and a runnable procedure checks a reader task.

## Action registry

<!-- sourcebound:begin actions -->
| name | audience |
| --- | --- |
| report | operators |
| inspect | maintainers |
<!-- sourcebound:end actions -->

Change the registry without repairing this table. The source-bound check must fail; the other two checks should not pretend to own that relationship.
