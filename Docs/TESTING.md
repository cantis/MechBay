# Testing Guide

Comprehensive testing documentation for MechBay service layer tests.

## Quick Start

```powershell
# Run all tests
uv run pytest tests/

# Run only unit tests (fast)
uv run pytest tests/*_unit.py

# Run only integration tests (slow)
uv run pytest tests/*_integration.py -m slow

# Run with parallel execution
uv run pytest tests/ -n auto

# Run specific test file
uv run pytest tests/test_force_service_unit.py -v

# Run specific test
uv run pytest tests/test_force_service_unit.py::test_create_force_becomes_active -v
```

## Test Organization

### Unit Tests vs Integration Tests

Tests are split into separate files for faster feedback during development:

- **Unit Tests** (`*_unit.py`): Fast tests using minimal fixtures
  - Test individual functions in isolation
  - Use `minimal_force` fixture (1 lance × 2 mechs)
  - No `@pytest.mark.slow` decorator
  - Average runtime: ~0.5 seconds

- **Integration Tests** (`*_integration.py`): Comprehensive tests with realistic data
  - Test complex multi-step operations
  - Use `realistic_force` (4 lances × 4 mechs) and `multiple_forces` fixtures
  - All tests marked with `@pytest.mark.slow`
  - Average runtime: ~2-3 seconds

### Test Files

```
tests/
├── conftest.py                              # Shared fixtures and helpers
├── test_force_service_unit.py               # Force service unit tests (19 tests)
├── test_force_service_integration.py        # Force service integration tests (16 tests)
├── test_lance_template_service_unit.py      # Template service unit tests (9 tests)
├── test_lance_template_service_integration.py  # Template service integration tests (11 tests)
├── test_miniatures.py                       # Miniature service tests (6 tests)
└── TEST_RESULTS.md                          # Test results and known issues
```

## Fixtures

### Core Fixtures

- **`app`**: Function-scoped Flask app with in-memory SQLite database
- **`client`**: Flask test client for making requests
- **`clear_seed_data`**: Autouse fixture that clears database before each test

### Data Fixtures

- **`sample_miniatures`**: Creates 20 varied mechs across different factions
  - Uses dynamic series values to prevent UNIQUE constraint violations
  - Returns list of miniature IDs

- **`minimal_force`**: Fast fixture for unit tests
  - 1 force with 1 lance containing 2 miniatures
  - Returns force ID

- **`realistic_force`**: Realistic fixture for integration tests
  - 1 force with 4 lances, each containing 4 miniatures (16 total)
  - All miniatures from same faction (Clan Wolf)
  - Returns force ID

- **`multiple_forces`**: Complex fixture for multi-force tests
  - 3 forces with different factions and sizes
  - Returns dict: `{"force1_id": int, "force2_id": int, "force3_id": int}`

- **`sample_template`**: Standard assault lance template
  - Contains chassis patterns for pattern matching tests
  - Returns LanceTemplate object

### Helper Functions

- **`validate_expunged_object(obj, *attributes)`**: Validates session.expunge() worked correctly
- **`assert_single_active_force(forces)`**: Validates exactly one force is active
- **`assert_force_structure(force, expected_lance_count, expected_miniature_count)`**: Validates force structure

## Running Tests

### Local Development

```powershell
# Fast feedback loop - unit tests only
uv run pytest tests/*_unit.py -v

# Full test suite
uv run pytest tests/ -v

# Watch mode (requires pytest-watch)
uv run pytest-watch tests/

# Stop on first failure
uv run pytest tests/ -x

# Run last failed tests only
uv run pytest tests/ --lf

# Verbose output with full tracebacks
uv run pytest tests/ -vv --tb=long
```

### Parallel Execution

Tests are isolated and can run in parallel using pytest-xdist:

```powershell
# Auto-detect CPU count
uv run pytest tests/ -n auto

# Specific number of workers
uv run pytest tests/ -n 4

# Distribute by test file (load balancing)
uv run pytest tests/ -n auto --dist=loadfile
```

### Filtering Tests

```powershell
# Run only slow integration tests
uv run pytest tests/ -m slow

# Run only fast unit tests (exclude slow)
uv run pytest tests/ -m "not slow"

# Run tests matching pattern
uv run pytest tests/ -k "create_force"

# Run tests in specific file matching pattern
uv run pytest tests/test_force_service_unit.py -k "active"
```

## Writing New Tests

### Test Structure

```python
def test_descriptive_name(client, fixture_name):
    \"\"\"Brief description of what this test validates.\"\"\"
    # Arrange: Set up test data
    force = create_force("Test Force")

    # Act: Perform the operation
    result = some_operation(force.id)

    # Assert: Verify expectations
    assert result is not None
    assert result.id > 0
```

### When to Use Unit vs Integration Tests

**Use Unit Tests** when:
- Testing a single function's behavior
- Edge cases and error handling
- Function returns specific values/types
- Test should run in < 100ms

**Use Integration Tests** when:
- Testing multi-step workflows
- Validating cascade behavior (deletes, updates)
- Testing with realistic data structures (4+ lances)
- Verifying complex relationships

### Marking Integration Tests

Add `@pytest.mark.slow` decorator to integration tests:

```python
@pytest.mark.slow
def test_complex_operation(client, realistic_force):
    \"\"\"Integration test with realistic force structure.\"\"\"
    # Test implementation
```

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Push to `main`, `develop`, or `cantis/**` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

Workflow stages:
1. **Unit Tests**: Run on Ubuntu, Windows, macOS with Python 3.14
2. **Integration Tests**: Run on Ubuntu after unit tests pass
3. **Parallel Tests**: Full suite with pytest-xdist after all tests pass

### Viewing Results

- Test results uploaded as artifacts (retained 7 days)
- Test summary in GitHub Actions job summary
- Failed tests show in PR checks

## Troubleshooting

### Common Issues

**Issue**: `NameError: name 'random' is not defined`
- **Cause**: Missing import in conftest.py
- **Fix**: Ensure `import random` at top of conftest.py

**Issue**: `UNIQUE constraint failed: miniatures.series, miniatures.unique_id`
- **Cause**: Hardcoded series values in fixture
- **Fix**: Fixture uses `f"TEST_{random.randint(1000, 9999)}"` for dynamic series

**Issue**: `DetachedInstanceError: Parent instance is not bound to a Session`
- **Cause**: Service function doesn't eager load relationships before `session.expunge()`
- **Fix**: Access relationships within session context before expunge:
  ```python
  force = Force(name=name)
  session.add(force)
  session.flush()
  _ = force.lances  # Eager load
  session.expunge(force)
  return force
  ```

**Issue**: Tests pass in isolation but fail when run together
- **Cause**: Data leak between tests
- **Fix**: Ensure `clear_seed_data` autouse fixture properly clears all tables

### Debugging Tests

```powershell
# Run single test with full output
uv run pytest tests/test_force_service_unit.py::test_create_force_becomes_active -vv --tb=long

# Drop into debugger on failure
uv run pytest tests/ --pdb

# Show print statements
uv run pytest tests/ -s

# Show local variables in traceback
uv run pytest tests/ --showlocals
```

## Test Coverage

Current coverage (as of test suite creation):
- **force_service.py**: 15/15 functions covered (100%)
- **lance_template_service.py**: 9/9 functions covered (100%)
- **miniature_service.py**: Partial coverage (existing tests)

Run coverage report:
```powershell
uv run pytest tests/ --cov=app.services --cov-report=html
# Open htmlcov/index.html in browser
```

## Known Issues

See [TEST_RESULTS.md](TEST_RESULTS.md) for:
- Current test pass/fail status
- Known edge cases and limitations
- Resolved issues from initial test creation

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [SQLAlchemy testing documentation](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#when-do-i-construct-a-session-when-do-i-commit-it-and-when-do-i-close-it)
