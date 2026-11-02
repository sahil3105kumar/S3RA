"""drop near duplicate chunks before insert.

use cosine similarity on embeddings, not exact text matching.
this catches semantically same chunks from extraction noise.
"""

import numpy as np

DEFAULT_SIMILARITY_THRESHOLD = 0.95


def filter_near_duplicates(
    items: list,
    embeddings: list[list[float]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[list, list[list[float]]]:
    """keep the first item from each near duplicate group.

    items and embeddings must align by index.
    returns filtered items and embeddings in original order.
    """
    if not items:
        return items, embeddings

    matrix = np.array(embeddings, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12  # avoid divide by zero for zero vectors.
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
