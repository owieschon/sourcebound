# Complementary toolchain fixture

This fixture executes two checks with distinct owners. A source-bound table tracks the action registry, and an editorial rule checks a wording constraint. Procedure runners are separate tools with their own pinned execution environment and receipts.

## Action registry

<!-- sourcebound:begin actions -->
| name | audience |
| --- | --- |
| report | operators |
| inspect | maintainers |
<!-- sourcebound:end actions -->

Change the registry without repairing this table. The source-bound check must fail; the editorial check should not pretend to own that relationship.
