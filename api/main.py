import os
import httpx
import psycopg2
from qdrant_client import QdrantClient
from fastapi import FastAPI

app = FastAPI(title="EPC Intelligence API")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
POSTGRES_URL = os.getenv("POSTGRES_URL")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


@app.get("/health")
async def health():
    status = {}

    # Check Ollama
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            status["ollama"] = "ok" if models else "no models loaded"
            status["ollama_models"] = models
    except Exception as e:
        status["ollama"] = f"error: {e}"

    # Check Postgres
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        conn.close()
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"error: {e}"

    # Check Qdrant
    try:
        client = QdrantClient(url=QDRANT_URL)
        client.get_collections()
        status["qdrant"] = "ok"
    except Exception as e:
        status["qdrant"] = f"error: {e}"

    overall = "ok" if all(v == "ok" or isinstance(v, list) 
                          for k, v in status.items() 
                          if k != "ollama_models") else "degraded"
    return {"status": overall, "services": status}