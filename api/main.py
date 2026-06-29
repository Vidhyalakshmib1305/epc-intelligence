import os
import uuid
import httpx  # pyright: ignore[reportMissingImports]
import psycopg2  # pyright: ignore[reportMissingModuleSource]
import pdfplumber  # pyright: ignore[reportMissingImports]
from pathlib import Path
from qdrant_client import QdrantClient  # pyright: ignore[reportMissingImports]
from qdrant_client.models import Distance, VectorParams, PointStruct  # pyright: ignore[reportMissingImports]
from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]
from fastapi import FastAPI, UploadFile, File, HTTPException  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel  # pyright: ignore[reportMissingImports]

app = FastAPI(title="EPC Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL   = os.getenv("OLLAMA_URL",  "http://localhost:11434")
POSTGRES_URL = os.getenv("POSTGRES_URL")
QDRANT_URL   = os.getenv("QDRANT_URL",  "http://localhost:6333")
UPLOAD_DIR   = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

COLLECTION   = "epc_documents"
CHUNK_SIZE   = 100
CHUNK_OVERLAP = 20

embedder = SentenceTransformer("all-MiniLM-L6-v2")


def get_db():
    return psycopg2.connect(POSTGRES_URL)


def get_qdrant():
    return QdrantClient(url=QDRANT_URL)


def init_db():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            doc_type    TEXT,
            page_count  INTEGER,
            uploaded_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def init_qdrant():
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )


def chunk_text(text: str) -> list[str]:
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunks.append(" ".join(words[start:end]))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if len(c.strip()) > 50]


@app.on_event("startup")
def startup():
    init_db()
    init_qdrant()


@app.get("/health")
async def health():
    status = {}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            status["ollama"] = "ok"
            status["ollama_models"] = models
    except Exception as e:
        status["ollama"] = f"error: {e}"
    try:
        conn = get_db()
        conn.close()
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"error: {e}"
    try:
        client = get_qdrant()
        cols = [c.name for c in client.get_collections().collections]
        status["qdrant"] = "ok"
        status["qdrant_collections"] = cols
    except Exception as e:
        status["qdrant"] = f"error: {e}"
    overall = "ok" if all(
        v == "ok" or isinstance(v, list)
        for k, v in status.items()
        if k not in ("ollama_models", "qdrant_collections")
    ) else "degraded"
    return {"status": overall, "services": status}


@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = "general"
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    doc_id    = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{doc_id}.pdf"
    contents  = await file.read()
    save_path.write_bytes(contents)

    full_text = ""
    with pdfplumber.open(save_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO documents (id, filename, doc_type, page_count) VALUES (%s,%s,%s,%s)",
        (doc_id, file.filename, doc_type, page_count)
    )
    conn.commit()
    cur.close()
    conn.close()

    chunks   = chunk_text(full_text)
    vectors  = embedder.encode(chunks).tolist()
    points   = [
        PointStruct(
            id      = str(uuid.uuid4()),
            vector  = vectors[i],
            payload = {
                "doc_id":   doc_id,
                "filename": file.filename,
                "doc_type": doc_type,
                "chunk_index": i,
                "text":     chunks[i]
            }
        )
        for i in range(len(chunks))
    ]
    get_qdrant().upsert(collection_name=COLLECTION, points=points)

    return {
        "doc_id":      doc_id,
        "filename":    file.filename,
        "doc_type":    doc_type,
        "page_count":  page_count,
        "chunks_stored": len(chunks),
        "preview":     full_text[:300]
    }


@app.get("/documents")
def list_documents():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, filename, doc_type, page_count, uploaded_at "
        "FROM documents ORDER BY uploaded_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "filename": r[1], "doc_type": r[2],
         "page_count": r[3], "uploaded_at": str(r[4])}
        for r in rows
    ]


@app.get("/documents/{doc_id}/chunks")
def get_chunks(doc_id: str):
    results = get_qdrant().scroll(
        collection_name=COLLECTION,
        scroll_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    return {"chunks": [p.payload for p in results[0]]}

class QueryRequest(BaseModel):
    question: str
    doc_type: str = None
    top_k: int = 5


@app.post("/query")
async def query_documents(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()

    search_filter = None
    if req.doc_type:
        search_filter = {
            "must": [{"key": "doc_type", "match": {"value": req.doc_type}}]
        }

    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=req.top_k,
        query_filter=search_filter,
        with_payload=True
    )

    if not results:
        return {"answer": "No relevant documents found.", "sources": []}

    context = ""
    sources = []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({
            "filename": r.payload["filename"],
            "doc_type": r.payload["doc_type"],
            "chunk_index": r.payload["chunk_index"],
            "score": round(r.score, 3),
            "text_preview": r.payload["text"][:200]
        })

    prompt = f"""You are an EPC project intelligence assistant. 
Answer the question using ONLY the context below. 
For each fact you state, reference the source number in brackets like [Source 1].
If the answer is not in the context, say "Not found in uploaded documents."

Context:
{context}

Question: {req.question}

Answer:"""

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False}
        )
        answer = response.json().get("response", "No response from model")

    return {"answer": answer, "sources": sources}