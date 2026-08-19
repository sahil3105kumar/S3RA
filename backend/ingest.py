import os
from supabase import create_client
from sentence_transformers import SentenceTransformer

from data.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
model = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text, size=300):
    words = text.split()
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def ingest_file(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_text(text)
    embeddings = model.encode(chunks).tolist()
    rows = [
        {"content": c, "metadata": {"source": os.path.basename(path)}, "embedding": e}
        for c, e in zip(chunks, embeddings)
    ]
    supabase.table("documents").insert(rows).execute()
    print(f"Inserted {len(rows)} chunks from {path}")

if __name__ == "__main__":
    ingest_file("data/test.txt")