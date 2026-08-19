"""Drop near-duplicate chunks before they get inserted.

Uses cosine similarity between chunk embeddings rather than exact text
matching, since PDF extraction can produce chunks that differ only in
whitespace/punctuation but are semantically identical -- and because we've
already computed the embeddings for insertion, this check is essentially free.
"""

import numpy as np

DEFAULT_SIMILARITY_THRESHOLD = 0.95


def filter_near_duplicates(
    items: list,
    embeddings: list[list[float]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[list, list[list[float]]]:
    """Greedily keep the first occurrence of each near-duplicate group.

    `items` and `embeddings` must be the same length and in the same order
    (e.g. items = chunk texts or Chunk objects, embeddings = their vectors).
    Returns the filtered (items, embeddings), preserving original order.
    """
    if not items:
        return items, embeddings

    matrix = np.array(embeddings, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12  # avoid divide-by-zero for a degenerate zero vector
    normalized = matrix / norms

    kept_indices: list[int] = []
    kept_vectors: list[np.ndarray] = []

    for i, vec in enumerate(normalized):
        is_duplicate = False
        if kept_vectors:
            sims = np.stack(kept_vectors) @ vec
            if sims.max() >= threshold:
                is_duplicate = True
        if not is_duplicate:
            kept_indices.append(i)
            kept_vectors.append(vec)

    filtered_items = [items[i] for i in kept_indices]
    filtered_embeddings = [embeddings[i] for i in kept_indices]
    return filtered_items, filtered_embeddings
