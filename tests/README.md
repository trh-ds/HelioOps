# tests/ — Test Suite

64 tests covering all HelioOps layers.

## Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_option_c.py` | 51 | CV detection, fusion, preprocessing, DONKI, flare, L1 |
| `test_pipeline.py` | 13 | ML inference, schema adapter, pipeline integration |
| `test_cv_preprocessing.py` | — | CV preprocessing unit tests |
| `test_retrieval.py` | — | RAG retrieval tests |

## Running

```bash
# All tests
pytest tests/ -v

# By layer
pytest tests/test_option_c.py -v      # CV detection
pytest tests/test_pipeline.py -v       # Backend pipeline
pytest tests/test_retrieval.py -v      # RAG retrieval

# Single test class
pytest tests/test_pipeline.py::TestMLInference -v
pytest tests/test_pipeline.py::TestAdapter -v
pytest tests/test_pipeline.py::TestFullPipeline -v
```

## Fixtures

- `tests/fixtures/march_2024_g4.json` — G4 storm fixture data
- `tests/conftest.py` — shared pytest configuration
