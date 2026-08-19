from supabase import create_client
from sentence_transformers import SentenceTransformer
from ddgs import DDGS

from backend.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
model = SentenceTransformer("all-MiniLM-L6-v2")

def search_internal_db(query: str, top_k=3):
    query_embedding = model.encode([query])[0].tolist()
    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": top_k
    }).execute()
    return result.data

def search_the_web(query: str, top_k=3):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=top_k))
    return "\n\n".join(f"{r['title']}: {r['body']}" for r in results)