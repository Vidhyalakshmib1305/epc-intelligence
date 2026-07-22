import io
import os
import uuid
import httpx  # pyright: ignore[reportMissingImports]
import psycopg2  # pyright: ignore[reportMissingModuleSource]
import pdfplumber  # pyright: ignore[reportMissingImports]
from pathlib import Path
from qdrant_client import QdrantClient  # pyright: ignore[reportMissingImports]
from qdrant_client.models import Distance, VectorParams, PointStruct  # pyright: ignore[reportMissingImports]
from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks  # pyright: ignore[reportMissingImports]
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
            chunk_count INTEGER,
            uploaded_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_questions (
            id              TEXT PRIMARY KEY,
            doc_id          TEXT REFERENCES documents(id) ON DELETE CASCADE,
            filename        TEXT NOT NULL,
            doc_type        TEXT NOT NULL,
            question        TEXT NOT NULL,
            expected_answer TEXT,
            validated       BOOLEAN DEFAULT FALSE,
            rejected        BOOLEAN DEFAULT FALSE,
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id               TEXT PRIMARY KEY,
            total_questions  INTEGER,
            hit_at_1         FLOAT,
            hit_at_3         FLOAT,
            hit_at_5         FLOAT,
            mrr              FLOAT,
            avg_faithfulness FLOAT,
            run_at           TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id                TEXT PRIMARY KEY,
            run_id            TEXT REFERENCES eval_runs(id) ON DELETE CASCADE,
            question_id       TEXT REFERENCES eval_questions(id) ON DELETE CASCADE,
            question          TEXT,
            expected_source   TEXT,
            retrieved_sources TEXT[],
            hit_at_1          BOOLEAN,
            hit_at_3          BOOLEAN,
            hit_at_5          BOOLEAN,
            reciprocal_rank   FLOAT,
            faithfulness      FLOAT,
            generated_answer  TEXT,
            created_at        TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def init_qdrant():
    import time
    for attempt in range(12):
        try:
            client = get_qdrant()
            existing = [c.name for c in client.get_collections().collections]
            if COLLECTION not in existing:
                client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
                print(f"Created collection: {COLLECTION}")
            else:
                print(f"Collection {COLLECTION} already exists")
            return
        except Exception as e:
            print(f"Qdrant not ready (attempt {attempt+1}/12): {e}")
            time.sleep(5)
    raise RuntimeError("Could not connect to Qdrant after 12 attempts")


def dedupe_results(results, top_k, max_chunks_per_doc=2):
    """Keep up to max_chunks_per_doc chunks per filename, sorted by score.

    Allowing 2 chunks per doc improves faithfulness (Mistral sees more of the
    correct document) without affecting Hit rate (document-level retrieval is
    unchanged — the right filename still appears in results).
    Results from Qdrant are already score-sorted, so we preserve that order.
    """
    seen = {}   # filename -> count of chunks kept so far
    kept = []
    for r in results:
        fname = r.payload.get('filename', '')
        count = seen.get(fname, 0)
        if count < max_chunks_per_doc:
            kept.append(r)
            seen[fname] = count + 1
    return kept[:top_k]


async def generate_eval_questions(doc_id: str, filename: str, doc_type: str, text: str) -> int:
    """Generate Q&A pairs from a document and store them in eval_questions. Returns count stored."""
    prompt = (
        "You are creating evaluation questions for a RAG retrieval system.\n"
        "Given the document excerpt below, generate EXACTLY 5 question-answer pairs.\n"
        "Requirements:\n"
        "- Each question must be answerable ONLY from this document\n"
        "- Questions must be specific (include document numbers, names, values where present)\n"
        "- Vary question types: what, which, how many, what is the status of, etc.\n"
        "- Answers must be concise (1-3 sentences)\n\n"
        "Output EXACTLY this format — no preamble, no explanation:\n"
        "Q1: <question>\nA1: <answer>\n"
        "Q2: <question>\nA2: <answer>\n"
        "Q3: <question>\nA3: <answer>\n"
        "Q4: <question>\nA4: <answer>\n"
        "Q5: <question>\nA5: <answer>\n\n"
        f"Document: {filename}\nType: {doc_type}\n\nContent:\n{text[:4000]}"
    )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 1000}
            )
            raw = r.json().get("response", "")

        # Parse Q/A pairs with regex
        import re
        pairs = re.findall(r'Q\d+:\s*(.+?)\nA\d+:\s*(.+?)(?=\nQ\d+:|\Z)', raw, re.DOTALL)
        if not pairs:
            return 0

        conn = get_db()
        cur  = conn.cursor()
        count = 0
        for q, a in pairs:
            q, a = q.strip(), a.strip()
            if len(q) > 10 and len(a) > 5:
                cur.execute(
                    "INSERT INTO eval_questions (id, doc_id, filename, doc_type, question, expected_answer) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), doc_id, filename, doc_type, q, a)
                )
                count += 1
        conn.commit()
        cur.close()
        conn.close()
        print(f"Generated {count} eval questions for {filename}")
        return count
    except Exception as e:
        print(f"Eval question generation failed for {filename}: {e}")
        return 0


async def score_faithfulness(answer: str, context: str) -> float:
    """Ask Mistral to rate how well the answer is grounded in the context (0.0–1.0)."""
    prompt = (
        "You are evaluating a RAG system's answer for faithfulness.\n"
        "Faithfulness = every claim in the answer is directly supported by the context.\n\n"
        f"CONTEXT:\n{context[:3000]}\n\n"
        f"ANSWER:\n{answer[:1000]}\n\n"
        "Score the answer's faithfulness from 0 to 10, where:\n"
        "10 = every claim is explicitly in the context\n"
        "5  = some claims supported, some not verifiable\n"
        "0  = answer contradicts or ignores the context\n\n"
        "Reply with ONLY a single integer (0-10). No explanation."
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 5}
            )
            raw = r.json().get("response", "5").strip()
            import re
            m = re.search(r'\d+', raw)
            score = int(m.group()) if m else 5
            return round(min(max(score, 0), 10) / 10.0, 2)
    except Exception:
        return 0.5


async def rewrite_query(question: str) -> str:
    """Rewrite a conversational question into retrieval-optimised keyword terms.
    Falls back to the original question if Ollama is slow or fails."""
    prompt = (
        "You are a search query optimizer for EPC data centre construction documents.\n"
        "Rewrite the question below as a short, keyword-rich search phrase that will retrieve "
        "the most relevant document chunks from a vector index.\n"
        "Rules: output ONLY the rewritten query on a single line. No explanation. No quotes.\n\n"
        f"Question: {question}\n"
        "Search query:"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 60}
            )
            rewritten = r.json().get("response", "").strip().splitlines()[0].strip()
            return rewritten if len(rewritten) > 4 else question
    except Exception:
        return question   # safe fallback — original question used instead


def chunk_text(text):
    words = text.split()
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
    services = {}

    # Qdrant
    try:
        client = get_qdrant()
        info = client.get_collection(COLLECTION)
        services["qdrant"] = {"status": "ok", "documents": info.points_count}
    except Exception as e:
        services["qdrant"] = {"status": "error", "message": str(e)}

    # Ollama + model check
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            has_mistral = any("mistral" in m for m in models)
            services["ollama"] = {
                "status": "ok" if has_mistral else "model_not_ready",
                "mistral_ready": has_mistral,
                "models": models
            }
    except Exception as e:
        services["ollama"] = {"status": "error", "mistral_ready": False, "message": str(e)}

    # Postgres
    try:
        conn = get_db()
        conn.cursor().execute("SELECT 1")
        services["postgres"] = {"status": "ok"}
    except Exception as e:
        services["postgres"] = {"status": "error", "message": str(e)}

    overall = "ok" if all(
        s.get("status") == "ok" for s in services.values()
    ) else "degraded"
    return {"status": overall, "services": services}


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), doc_type: str = Form(...)):  # pyright: ignore[reportUndefinedVariable]
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

    try:
        pdf_doc = pdfplumber.open(io.BytesIO(content))
        if len(pdf_doc.pages) == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupt PDF file.")

    try:
        text = ""
        for page in pdf_doc.pages:
            text += page.extract_text() or ""
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF appears to be scanned/image-only. Text extraction not supported yet.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")

    # chunk + embed + store (rest of your existing upload logic here)
    chunks = [text[i:i+500] for i in range(0, len(text), 400)]
    doc_id = str(uuid.uuid4())
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (id, filename, doc_type, page_count, chunk_count) VALUES (%s, %s, %s, %s, %s)",
        (doc_id, file.filename, doc_type, len(pdf_doc.pages), len(chunks))
    )
    conn.commit()

    points = []
    for i, chunk in enumerate(chunks):
        vector = embedder.encode(chunk).tolist()
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"filename": file.filename, "doc_type": doc_type,
                     "chunk_index": i, "text": chunk, "doc_id": doc_id}
        ))
    get_qdrant().upsert(collection_name=COLLECTION, points=points)

    # Generate eval Q&A pairs from first 4000 chars of document text (async, best-effort)
    import asyncio
    asyncio.create_task(generate_eval_questions(doc_id, file.filename, doc_type, text))

    return {"id": doc_id, "filename": file.filename, "doc_type": doc_type,
            "chunks_stored": len(chunks), "page_count": len(pdf_doc.pages),
            "eval_questions_generating": True}

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

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512}
        )
        answer = response.json().get("response", "No response from model")

    return {"answer": answer, "sources": sources}

@app.post("/query/stream")
async def query_documents_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()

    search_filter = None
    if req.doc_type:
        search_filter = {"must": [{"key": "doc_type", "match": {"value": req.doc_type}}]}

    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=req.top_k * 4,
        query_filter=search_filter,
        with_payload=True
    )
    results = dedupe_results(results, req.top_k)

    if not results:
        async def empty():
            yield "No relevant documents found."
        return StreamingResponse(empty(), media_type="text/plain")

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

    async def generate():
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": True}
            ) as r:
                async for line in r.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if not data.get("done"):
                                token = data.get("response", "")
                                if token:
                                    yield token
                        except Exception:
                            pass
        yield f'\n\n__META__{json.dumps({"rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/spec-compliance")
async def spec_compliance_agent(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "specification"}}]},
        with_payload=True
    )
    if not results:
        return {"compliance_status": "unknown", "answer": "No specification documents found.", "sources": []}

    context = ""
    sources = []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({
            "filename": r.payload["filename"],
            "chunk_index": r.payload["chunk_index"],
            "score": round(r.score, 3),
            "text_preview": r.payload["text"][:200]
        })

    prompt = f"""You are a strict EPC specification compliance checker for data centre construction.
Analyse the following query against the specification documents provided.
Determine if there is a compliance requirement, what it states exactly, and flag any gaps or risks.
Format your response as:
REQUIREMENT: [what the spec says]
COMPLIANCE STATUS: [COMPLIANT / NON-COMPLIANT / REQUIRES VERIFICATION]
RISK: [any risk or gap identified]
SOURCE: [cite the source document and section]

Specification context:
{context}

Query: {req.question}

Analysis:"""

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512}
        )
        answer = r.json().get("response", "")

    compliance_status = "COMPLIANT" if "COMPLIANT" in answer and "NON-COMPLIANT" not in answer else \
                        "NON-COMPLIANT" if "NON-COMPLIANT" in answer else "REQUIRES VERIFICATION"

    return {"compliance_status": compliance_status, "analysis": answer, "sources": sources}


@app.post("/agents/schedule-risk")
async def schedule_risk_agent(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "schedule"}}]},
        with_payload=True
    )
    if not results:
        return {"risk_level": "unknown", "answer": "No schedule documents found.", "sources": []}

    context = ""
    sources = []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({
            "filename": r.payload["filename"],
            "chunk_index": r.payload["chunk_index"],
            "score": round(r.score, 3),
            "text_preview": r.payload["text"][:200]
        })

    prompt = f"""You are an EPC project schedule risk analyst for data centre construction.
Analyse the schedule information and identify risks, delays, and critical path impacts.
Format your response as:
RISK LEVEL: [HIGH / MEDIUM / LOW]
IDENTIFIED RISKS: [list each risk]
CRITICAL PATH IMPACT: [impact on project completion]
RECOMMENDATION: [what should be done]

Schedule context:
{context}

Query: {req.question}

Risk Analysis:"""

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512}
        )
        answer = r.json().get("response", "")

    risk_level = "HIGH" if "HIGH" in answer else "MEDIUM" if "MEDIUM" in answer else "LOW"

    return {"risk_level": risk_level, "analysis": answer, "sources": sources}


@app.post("/agents/rfi-copilot")
async def rfi_copilot_agent(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "rfi"}}]},
        with_payload=True
    )

    context = ""
    sources = []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({
            "filename": r.payload["filename"],
            "chunk_index": r.payload["chunk_index"],
            "score": round(r.score, 3),
            "text_preview": r.payload["text"][:200]
        })

    prompt = f"""You are an RFI (Request for Information) assistant for a data centre EPC project.
Search the RFI log for relevant past RFIs and provide answers with references.
If a similar RFI was resolved before, cite the resolution.
If the RFI is still open, flag it clearly.
Format your response as:
SIMILAR RFIs FOUND: [list relevant past RFIs]
ANSWER: [answer based on past RFI resolutions]
OPEN ITEMS: [any unresolved related RFIs]
RECOMMENDATION: [suggested next step]

RFI Log context:
{context}

Current query: {req.question}

RFI Analysis:"""

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512}
        )
        answer = r.json().get("response", "")

    return {"answer": answer, "sources": sources}

@app.post("/agents/spec-compliance/stream")
async def spec_compliance_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k * 4 or 20,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "specification"}}]},
        with_payload=True
    )
    results = dedupe_results(results, req.top_k or 5)
    if not results:
        async def empty():
            yield "No specification documents found."
            yield f'\n\n__META__{json.dumps({"compliance_status":"UNKNOWN"})}__SOURCES__[]'
        return StreamingResponse(empty(), media_type="text/plain")

    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3), "text_preview": r.payload["text"][:200]})

    prompt = f"""You are a strict EPC specification compliance checker for data centre construction.
Analyse the following query against the specification documents provided.
Format your response as:
REQUIREMENT: [what the spec says]
COMPLIANCE STATUS: [COMPLIANT / NON-COMPLIANT / REQUIRES VERIFICATION]
RISK: [any risk or gap identified]
SOURCE: [cite the source document and section]

Specification context:
{context}

Query: {req.question}

Analysis:"""

    async def generate():
        full_text = ""
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": True, "num_predict": 512}
            ) as r:
                async for line in r.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if not data.get("done"):
                                token = data.get("response", "")
                                if token:
                                    full_text += token
                                    yield token
                        except Exception:
                            pass
        status = "NON-COMPLIANT" if "NON-COMPLIANT" in full_text else \
                 "COMPLIANT" if "COMPLIANT" in full_text else "REQUIRES VERIFICATION"
        yield f'\n\n__META__{json.dumps({"compliance_status": status, "rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/schedule-risk/stream")
async def schedule_risk_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k * 4 or 20,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "schedule"}}]},
        with_payload=True
    )
    results = dedupe_results(results, req.top_k or 5)
    if not results:
        async def empty():
            yield "No schedule documents found."
            yield f'\n\n__META__{json.dumps({"risk_level":"UNKNOWN"})}__SOURCES__[]'
        return StreamingResponse(empty(), media_type="text/plain")

    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3), "text_preview": r.payload["text"][:200]})

    prompt = f"""You are an EPC project schedule risk analyst for data centre construction.
Analyse the schedule information and identify risks, delays, and critical path impacts.
Format your response as:
RISK LEVEL: [HIGH / MEDIUM / LOW]
IDENTIFIED RISKS: [list each risk]
CRITICAL PATH IMPACT: [impact on project completion]
RECOMMENDATION: [what should be done]

Schedule context:
{context}

Query: {req.question}

Risk Analysis:"""

    async def generate():
        full_text = ""
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": True, "num_predict": 512}
            ) as r:
                async for line in r.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if not data.get("done"):
                                token = data.get("response", "")
                                if token:
                                    full_text += token
                                    yield token
                        except Exception:
                            pass
        risk = "HIGH" if "HIGH" in full_text else "MEDIUM" if "MEDIUM" in full_text else "LOW"
        yield f'\n\n__META__{json.dumps({"risk_level": risk, "rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/rfi-copilot/stream")
async def rfi_copilot_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k * 4 or 20,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "rfi"}}]},
        with_payload=True
    )
    results = dedupe_results(results, req.top_k or 5)

    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3), "text_preview": r.payload["text"][:200]})

    prompt = f"""You are an RFI assistant for a data centre EPC project.
Search the RFI log for relevant past RFIs and provide answers with references.
Format your response as:
SIMILAR RFIs FOUND: [list relevant past RFIs]
ANSWER: [answer based on past RFI resolutions]
OPEN ITEMS: [any unresolved related RFIs]
RECOMMENDATION: [suggested next step]

RFI Log context:
{context}

Current query: {req.question}

RFI Analysis:"""

    async def generate():
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": True, "num_predict": 512}
            ) as r:
                async for line in r.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if not data.get("done"):
                                token = data.get("response", "")
                                if token:
                                    yield token
                        except Exception:
                            pass
        yield f'\n\n__META__{json.dumps({"rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/supply-chain")
async def supply_chain_agent(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "supply_chain"}}]},
        with_payload=True
    )
    if not results:
        return {"delivery_risk": "UNKNOWN", "answer": "No supply chain documents found.", "sources": []}

    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3)})

    prompt = f"""You are a supply chain risk analyst for a data centre EPC project.
Analyse procurement status. Identify at-risk deliveries.
Start your response with: DELIVERY RISK: [CRITICAL / AT RISK / ON TRACK]

Context:
{context}

Query: {req.question}

Analysis:"""

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512})
        answer = r.json().get("response", "")

    risk = "CRITICAL" if "CRITICAL" in answer else \
           "AT RISK" if "AT RISK" in answer or "HIGH" in answer else "ON TRACK"
    return {"delivery_risk": risk, "answer": answer, "sources": sources}


@app.post("/agents/supply-chain/stream")
async def supply_chain_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k * 4 or 20,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "supply_chain"}}]},
        with_payload=True
    )
    results = dedupe_results(results, req.top_k or 5)
    if not results:
        async def empty():
            yield "No supply chain documents found. Please upload procurement data first."
            yield f'\n\n__META__{json.dumps({"delivery_risk": "UNKNOWN"})}__SOURCES__[]'
        return StreamingResponse(empty(), media_type="text/plain")

    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3), "text_preview": r.payload["text"][:200]})

    prompt = f"""You are a supply chain risk analyst for a data centre EPC project.
Analyse the procurement status and identify at-risk equipment deliveries that could delay the project.
Format your response as:
DELIVERY RISK: [CRITICAL / AT RISK / ON TRACK]
AT-RISK ITEMS: [list each item with reason]
CRITICAL PATH IMPACT: [which activities are blocked]
RECOMMENDATION: [immediate actions required]

Procurement context:
{context}

Query: {req.question}

Supply Chain Analysis:"""

    async def generate():
        full_text = ""
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", f"{OLLAMA_URL}/api/generate",
                    json={"model": "mistral:7b", "prompt": prompt, "stream": True, "num_predict": 512}
                ) as r:
                    async for line in r.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if not data.get("done"):
                                    token = data.get("response", "")
                                    if token:
                                        full_text += token
                                        yield token
                            except Exception:
                                pass
        except httpx.ConnectError:
            yield "[ERROR: Cannot connect to Ollama. Check that the service is running.]"
            return
        except httpx.ReadTimeout:
            yield "[ERROR: Response timed out. Please retry.]"
            return

        risk = "CRITICAL" if "CRITICAL" in full_text else \
               "AT RISK" if "AT RISK" in full_text or "HIGH" in full_text else "ON TRACK"
        yield f'\n\n__META__{json.dumps({"delivery_risk": risk, "rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/commissioning-qa")
async def commissioning_qa_agent(req: QueryRequest):
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "commissioning"}}]},
        with_payload=True
    )
    if not results:
        return {"test_status": "UNKNOWN", "answer": "No commissioning documents found.", "sources": []}
    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"], "score": round(r.score, 3)})
    prompt = f"""You are a commissioning QA engineer for a data centre EPC project.
Analyse test results and non-conformances against TIA-942 and Tier III standards.
Start your response with: TEST STATUS: [PASS / FAIL / PARTIAL]
Context:\n{context}\nQuery: {req.question}\nAnalysis:"""
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral:7b", "prompt": prompt, "stream": False, "num_predict": 512})
        answer = r.json().get("response", "")
    status = "FAIL" if "FAIL" in answer else "PASS" if "PASS" in answer else "PARTIAL"
    return {"test_status": status, "answer": answer, "sources": sources}


@app.post("/agents/commissioning-qa/stream")
async def commissioning_qa_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]
    retrieval_query = await rewrite_query(req.question)
    question_vector = embedder.encode(retrieval_query).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k * 4 or 20,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "commissioning"}}]},
        with_payload=True
    )
    results = dedupe_results(results, req.top_k or 5)
    if not results:
        async def empty():
            yield "No commissioning documents found. Please upload commissioning QA data first."
            yield f'\n\n__META__{json.dumps({"test_status":"UNKNOWN"})}__SOURCES__[]'
        return StreamingResponse(empty(), media_type="text/plain")
    context, sources = "", []
    for i, r in enumerate(results):
        context += f"\n[Source {i+1}: {r.payload['filename']}]\n{r.payload['text']}\n"
        sources.append({"filename": r.payload["filename"], "chunk_index": r.payload["chunk_index"],
                        "score": round(r.score, 3), "text_preview": r.payload["text"][:200]})
    prompt = f"""You are a commissioning QA engineer for a data centre EPC project.
Analyse test results and non-conformances against TIA-942 and Uptime Institute Tier III standards.
Format your response as:
TEST STATUS: [PASS / FAIL / PARTIAL]
FAILED TESTS: [list any failed tests with NCR numbers]
OPEN NON-CONFORMANCES: [list open NCRs with severity]
TIER III READINESS: [summary of certification readiness]
RECOMMENDATION: [what must be resolved before Tier III audit]

Commissioning context:\n{context}\nQuery: {req.question}\nQA Analysis:"""

    async def generate():
        full_text = ""
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", f"{OLLAMA_URL}/api/generate",
                    json={"model": "mistral:7b", "prompt": prompt, "stream": True, "num_predict": 512}) as r:
                    async for line in r.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if not data.get("done"):
                                    token = data.get("response", "")
                                    if token:
                                        full_text += token
                                        yield token
                            except Exception:
                                pass
        except httpx.ConnectError:
            yield "[ERROR: Cannot connect to Ollama.]"
            return
        except httpx.ReadTimeout:
            yield "[ERROR: Response timed out. Please retry.]"
            return
        status = "FAIL" if "FAIL" in full_text else "PASS" if "PASS" in full_text else "PARTIAL"
        yield f'\n\n__META__{json.dumps({"test_status": status, "rewritten_query": retrieval_query, "retrieval_score": round(sum(s["score"] for s in sources) / len(sources), 3) if sources else 0.0})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


# ─────────────────────────────────────────────
#  EVAL ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/eval/questions")
def list_eval_questions(doc_id: str = None, validated: bool = None, rejected: bool = None):
    conn = get_db(); cur = conn.cursor()
    query = "SELECT id, doc_id, filename, doc_type, question, expected_answer, validated, rejected, created_at FROM eval_questions WHERE 1=1"
    params = []
    if doc_id:
        query += " AND doc_id = %s"; params.append(doc_id)
    if validated is not None:
        query += " AND validated = %s"; params.append(validated)
    if rejected is not None:
        query += " AND rejected = %s"; params.append(rejected)
    query += " ORDER BY created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall(); cur.close(); conn.close()
    return [{"id": r[0], "doc_id": r[1], "filename": r[2], "doc_type": r[3],
             "question": r[4], "expected_answer": r[5], "validated": r[6],
             "rejected": r[7], "created_at": str(r[8])} for r in rows]


class EvalQuestionPatch(BaseModel):
    validated: bool = None
    rejected: bool = None


@app.patch("/eval/questions/{question_id}")
def update_eval_question(question_id: str, body: EvalQuestionPatch):
    conn = get_db(); cur = conn.cursor()
    if body.validated is not None:
        cur.execute("UPDATE eval_questions SET validated=%s, rejected=FALSE WHERE id=%s",
                    (body.validated, question_id))
    if body.rejected is not None:
        cur.execute("UPDATE eval_questions SET rejected=%s, validated=FALSE WHERE id=%s",
                    (body.rejected, question_id))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


@app.delete("/eval/questions/{question_id}")
def delete_eval_question(question_id: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM eval_questions WHERE id=%s", (question_id,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


@app.post("/eval/questions/{doc_id}/generate")
async def generate_questions_for_doc(doc_id: str):
    """Generate (or re-generate) eval questions for an already-uploaded document."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT filename, doc_type FROM documents WHERE id=%s", (doc_id,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    filename, doc_type = row

    results = get_qdrant().scroll(
        collection_name=COLLECTION,
        scroll_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
        limit=50, with_payload=True, with_vectors=False
    )
    text = " ".join(p.payload.get("text", "") for p in results[0])

    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM eval_questions WHERE doc_id=%s AND validated=FALSE AND rejected=FALSE", (doc_id,))
    conn.commit(); cur.close(); conn.close()

    count = await generate_eval_questions(doc_id, filename, doc_type, text)
    return {"generated": count, "doc_id": doc_id, "filename": filename}


# ── Eval background state ──────────────────────────────────────────────────────
_eval_state = {"running": False, "last_run_id": None, "error": None}


async def _run_eval_background():
    """Execute eval for all validated questions and persist results. Runs as background task."""
    _eval_state["running"] = True
    _eval_state["error"] = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            SELECT id, doc_id, filename, doc_type, question, expected_answer
            FROM eval_questions WHERE validated=TRUE AND rejected=FALSE ORDER BY created_at
        """)
        questions = cur.fetchall(); cur.close(); conn.close()

        if not questions:
            _eval_state["error"] = "No validated questions found."
            return

        run_id = str(uuid.uuid4())
        results = []

        for q_id, doc_id, filename, doc_type, question, expected_answer in questions:
            retrieval_query = await rewrite_query(question)
            q_vec = embedder.encode(retrieval_query).tolist()
            hits = get_qdrant().search(
                collection_name=COLLECTION, query_vector=q_vec, limit=20,
                query_filter={"must": [{"key": "doc_type", "match": {"value": doc_type}}]},
                with_payload=True
            )
            hits = dedupe_results(hits, 5)
            retrieved_sources = [h.payload["filename"] for h in hits]
            rank = next((i + 1 for i, h in enumerate(hits) if h.payload["filename"] == filename), None)
            context = "\n".join(
                f"[Source {i+1}: {h.payload['filename']}]\n{h.payload['text']}"
                for i, h in enumerate(hits[:3])
            )
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    r = await client.post(f"{OLLAMA_URL}/api/generate",
                        json={"model": "mistral:7b", "prompt":
                            f"Answer using ONLY the context below.\nContext:\n{context}\n\nQuestion: {question}\nAnswer:",
                            "stream": False, "num_predict": 300})
                    generated_answer = r.json().get("response", "").strip()
            except Exception:
                generated_answer = ""
            faithfulness = await score_faithfulness(generated_answer, context)
            results.append({
                "id": str(uuid.uuid4()), "run_id": run_id, "question_id": q_id,
                "question": question, "expected_source": filename,
                "retrieved_sources": retrieved_sources,
                "hit_at_1": rank == 1,
                "hit_at_3": rank is not None and rank <= 3,
                "hit_at_5": rank is not None and rank <= 5,
                "reciprocal_rank": (1.0 / rank) if rank else 0.0,
                "faithfulness": faithfulness, "generated_answer": generated_answer,
            })

        n = len(results)
        summary = {
            "hit_at_1":         round(sum(r["hit_at_1"]       for r in results) / n, 3),
            "hit_at_3":         round(sum(r["hit_at_3"]       for r in results) / n, 3),
            "hit_at_5":         round(sum(r["hit_at_5"]       for r in results) / n, 3),
            "mrr":              round(sum(r["reciprocal_rank"] for r in results) / n, 3),
            "avg_faithfulness": round(sum(r["faithfulness"]    for r in results) / n, 3),
        }
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO eval_runs (id, total_questions, hit_at_1, hit_at_3, hit_at_5, mrr, avg_faithfulness) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (run_id, n, summary["hit_at_1"], summary["hit_at_3"], summary["hit_at_5"],
             summary["mrr"], summary["avg_faithfulness"])
        )
        for r in results:
            cur.execute(
                "INSERT INTO eval_results (id, run_id, question_id, question, expected_source, "
                "retrieved_sources, hit_at_1, hit_at_3, hit_at_5, reciprocal_rank, faithfulness, generated_answer) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (r["id"], r["run_id"], r["question_id"], r["question"], r["expected_source"],
                 r["retrieved_sources"], r["hit_at_1"], r["hit_at_3"], r["hit_at_5"],
                 r["reciprocal_rank"], r["faithfulness"], r["generated_answer"])
            )
        conn.commit(); cur.close(); conn.close()
        _eval_state["last_run_id"] = run_id
    except Exception as e:
        _eval_state["error"] = str(e)
    finally:
        _eval_state["running"] = False


@app.post("/eval/run")
async def run_eval(background_tasks: BackgroundTasks):
    """Start eval as a background task. Returns immediately. Poll /eval/status for progress."""
    if _eval_state["running"]:
        raise HTTPException(status_code=409, detail="Eval already running. Poll /eval/status.")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM eval_questions WHERE validated=TRUE AND rejected=FALSE")
    count = cur.fetchone()[0]; cur.close(); conn.close()
    if count == 0:
        raise HTTPException(status_code=400, detail="No validated questions found.")
    background_tasks.add_task(_run_eval_background)
    return {"status": "started", "total_questions": count,
            "message": "Eval running in background. Poll /eval/status for completion."}


@app.get("/eval/status")
def eval_status():
    """Check if an eval is currently running."""
    return {"running": _eval_state["running"], "last_run_id": _eval_state["last_run_id"],
            "error": _eval_state["error"]}


@app.get("/eval/runs")
def list_eval_runs():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT id, total_questions, hit_at_1, hit_at_3, hit_at_5, mrr, avg_faithfulness, run_at
                   FROM eval_runs ORDER BY run_at DESC LIMIT 20""")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [{"id": r[0], "total_questions": r[1], "hit_at_1": r[2], "hit_at_3": r[3],
             "hit_at_5": r[4], "mrr": r[5], "avg_faithfulness": r[6], "run_at": str(r[7])} for r in rows]


@app.get("/eval/runs/latest")
def latest_eval_run():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT id, total_questions, hit_at_1, hit_at_3, hit_at_5, mrr, avg_faithfulness, run_at
                   FROM eval_runs ORDER BY run_at DESC LIMIT 1""")
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return None
    return {"id": row[0], "total_questions": row[1], "hit_at_1": row[2], "hit_at_3": row[3],
            "hit_at_5": row[4], "mrr": row[5], "avg_faithfulness": row[6], "run_at": str(row[7])}


@app.get("/eval/runs/{run_id}/results")
def get_run_results(run_id: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT id, question_id, question, expected_source, retrieved_sources,
                          hit_at_1, hit_at_3, hit_at_5, reciprocal_rank, faithfulness, generated_answer
                   FROM eval_results WHERE run_id=%s ORDER BY created_at""", (run_id,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [{"id": r[0], "question_id": r[1], "question": r[2], "expected_source": r[3],
             "retrieved_sources": r[4], "hit_at_1": r[5], "hit_at_3": r[6], "hit_at_5": r[7],
             "reciprocal_rank": r[8], "faithfulness": r[9], "generated_answer": r[10]} for r in rows]