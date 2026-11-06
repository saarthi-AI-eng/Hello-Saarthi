"""Hybrid retrieval engine behind src.tools.retrieve.retrieve().

Legs (each optional, each fails soft):
  dense   FAISS similarity over the folder's embeddings
  bm25    pure-python BM25 over the same chunk texts (works with no embedding service)
  colbert late-interaction rerank of the candidate pool (RAGatouille; off unless installed + enabled)
  rerank  cross-encoder rerank of the fused list (sentence-transformers; off unless installed + enabled)

Dense + BM25 are fused with Reciprocal Rank Fusion (k=60). The two GPU legs only
reorder candidates that dense/BM25 already found inside the same index folder, so
they can never pull in out-of-scope chunks or drop an in-scope one.
"""
