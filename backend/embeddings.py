"""Embeddings via the Hugging Face Inference API instead of a local
sentence-transformers/torch install. Uses the same model
(all-MiniLM-L6-v2) so vector dimensions (384) and semantics are
unchanged -- no DB schema or re-embedding impact.
"""

from huggingface_hub import InferenceClient
from tokenizers import Tokenizer

from config import HF_TOKEN

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# The model's fixed max_seq_length per its sentence_bert_config.json.
# There's no local model object anymore to read this off of, so it's
# pinned directly -- this value is intrinsic to the model, not something
# that changes with library versions.
MODEL_MAX_SEQ_LENGTH = 256

_client = InferenceClient(provider="hf-inference", api_key=HF_TOKEN)
_tokenizer = Tokenizer.from_pretrained(MODEL_ID)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one 384-dim vector per input,
    in the same order."""
    result = _client.feature_extraction(texts, model=MODEL_ID)
    return result.tolist() if hasattr(result, "tolist") else list(result)


def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text).ids)