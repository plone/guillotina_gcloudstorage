# AGENTS.md

## Project Overview
- Purpose: Guillotina external file storage backend for Google Cloud Storage.
- Main stack: Python package, Guillotina integration, aiohttp/Google Cloud Storage APIs.
- Key paths:
  - `guillotina_gcloudstorage/storage.py`: storage manager implementation.
  - `guillotina_gcloudstorage/interfaces.py`: package interfaces.
  - `guillotina_gcloudstorage/tests/`: pytest coverage.

## Development Commands
- Install: `pip install -e '.[test]'`
- Pre-checks: `make pre-checks`
- Tests: `make tests`

## Validation
- CI runs `make pre-checks` on Python 3.10, 3.11, and 3.12.
- Some storage tests need Google Cloud credentials or mocked GCS behavior; avoid assuming the full test suite is runnable without that local setup.

## Deployment Notes
- This is a library package; there is no direct deployment from this repo.

## Constraints / Gotchas
- Keep changes scoped to package metadata, storage behavior, or tests as requested.
- Do not commit credentials or local environment files.

## Task Closeout Notes
- Record the branch name, commit hash, and validation commands used.
