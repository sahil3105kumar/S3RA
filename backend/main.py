from fastapi import FastAPI

from config import GROQ_API_KEY, SUPABASE_KEY, SUPABASE_URL

app = FastAPI(title="S3RA API")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "groq_configured": bool(GROQ_API_KEY),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
    }