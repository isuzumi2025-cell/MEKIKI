# 90_System - RAG Index

Vector embeddings and search index for RAG.

## Contents
- `embeddings.db` - SQLite with vectors
- `config.json` - Index settings

## Note
This folder can be excluded from Obsidian sync if needed.
Add to `.gitignore` for version control.

## Usage
```python
from rag_indexer import RAGIndexer
indexer = RAGIndexer(vault_dir="../")
indexer.build_index()
results = indexer.search("寺社めぐり")
```
