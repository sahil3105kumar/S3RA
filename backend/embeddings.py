"""embedding calls use hugging face inference, not local model runtime.
same model keeps 384 dim vectors and same semantics.
no db schema or re embedding changes needed.
"""

from huggingface_hub import InferenceClient
from tokenizers import Tokenizer

from config import HF_TOKEN

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# fixed model max sequence length.
# no local model object exists here, so keep this pinned.
MODEL_MAX_SEQ_LENGTH = 256

_client = InferenceClient(provider="hf-inference", api_key=HF_TOKEN)
_tokenizer = Tokenizer.from_pretrained(MODEL_ID)


def embed(texts: list[str]) -> list[list[float]]:
    """embed a batch of texts.
    returns one 384 dim vector per input in the same order.
    """
    result = _client.feature_extraction(texts, model=MODEL_ID)
    return result.tolist() if hasattr(result, "tolist") else list(result)


def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text).ids)