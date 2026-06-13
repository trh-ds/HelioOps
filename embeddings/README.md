# embeddings/ — RAG Knowledge Base Layer

ChromaDB vector store with BGE-small embeddings powering retrieval-augmented generation for industry advisories.

## Architecture

```
data/{aviation,grid,maritime,impact_matrix}/
  └── loaders.py → chunker.py → embedder.py (BGE-small) → ChromaDB collections
                                                              ├── aviation_kb     (242 chunks)
                                                              ├── grid_kb         (101 chunks)
                                                              ├── impact_matrix_kb (166 chunks)
                                                              ├── maritime_kb     (2 chunks)
                                                              └── telecom_kb      (0 chunks)
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | ChromaDB path, collection names |
| `embedder.py` | BGE-small embedding wrapper |
| `chunker.py` | Document chunking with overlap |
| `loaders.py` | PDF/text/markdown document loaders |
| `cache.py` | Embedding cache for repeated queries |
| `collections.py` | ChromaDB collection management |
| `retrieval.py` | Query interface — embed query → cosine search → format context |
| `ingest_aviation.py` | Ingest aviation knowledge base (ICAO, NAT Doc 007) |
| `ingest_grid.py` | Ingest power grid KB (NERC, GIC standards) |
| `ingest_impact_matrix.py` | Ingest NOAA impact severity matrix |
| `ingest_maritime.py` | Ingest maritime KB (GMDSS, IMO) |

## Usage

```python
from embeddings.retrieval import retrieve

# Query with storm context
chunks = retrieve("G4 storm GPS impact on aviation", collection="aviation_kb", top_k=8)
```

## Configuration

- **Persist path**: `./data/chroma_db/`
- **Embedding model**: BGE-small (384-dim)
- **RAG top-k**: 8 (set in `genai/config.py`)
- **Min similarity**: 0.35 cosine threshold
