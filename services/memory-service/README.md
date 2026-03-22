# Memory Service

This directory is now a legacy pre-split boundary.

The PoC has been refactored into:

- [context-memory-service](../context-memory-service/README.md) for the current operational task snapshot
- [provenance-service](../provenance-service/README.md) for append-only provenance, artifacts, and delegation records

New work should target those two services instead of extending this combined boundary.
