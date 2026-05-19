"""
Embedding Utility for Competitor Intelligence RAG
Uses qwen3-embedding:4b via Ollama (user's preferred model)
"""

import ollama
from typing import List
import numpy as np
import logging
logger = logging.getLogger(__name__)

MODEL = "nomic-embed-text"

def get_embedding(text: str) -> List[float]:
    """Generate embedding for a single text using nomic-embed-text via Ollama."""
    if not text or not text.strip():
        return [0.0] * 768
    
    try:
        response = ollama.embeddings(model=MODEL, prompt=text.strip())
        return response["embedding"]
    except Exception as e:
        logger.error("Embedding error for model %s: %s", MODEL, e)
        return [0.0] * 768

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    embeddings = []
    for text in texts:
        emb = get_embedding(text)
        embeddings.append(emb)
    return embeddings

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two embeddings."""
    arr_a = np.array(a)
    arr_b = np.array(b)
    return float(np.dot(arr_a, arr_b) / (np.linalg.norm(arr_a) * np.linalg.norm(arr_b) + 1e-8))