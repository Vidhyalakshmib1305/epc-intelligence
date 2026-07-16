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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException  # pyright: ignore[reportMissingImports]
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

    return {"id": doc_id, "filename": file.filename, "doc_type": doc_type,
            "chunks_stored": len(chunks), "page_count": len(pdf_doc.pages)}

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

    question_vector = embedder.encode(req.question).tolist()

    search_filter = None
    if req.doc_type:
        search_filter = {"must": [{"key": "doc_type", "match": {"value": req.doc_type}}]}

    results = get_qdrant().search(
        collection_name=COLLECTION,
        query_vector=question_vector,
        limit=req.top_k,
        query_filter=search_filter,
        with_payload=True
    )

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
        yield f"\n\n__SOURCES__{json.dumps(sources)}"

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

    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "specification"}}]},
        with_payload=True
    )
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
        yield f'\n\n__META__{json.dumps({"compliance_status": status})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/schedule-risk/stream")
async def schedule_risk_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "schedule"}}]},
        with_payload=True
    )
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
        yield f'\n\n__META__{json.dumps({"risk_level": risk})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agents/rfi-copilot/stream")
async def rfi_copilot_stream(req: QueryRequest):
    import json
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]

    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "rfi"}}]},
        with_payload=True
    )

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
        yield f'\n\n__META__{json.dumps({})}__SOURCES__{json.dumps(sources)}'

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

    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "supply_chain"}}]},
        with_payload=True
    )
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
        yield f'\n\n__META__{json.dumps({"delivery_risk": risk})}__SOURCES__{json.dumps(sources)}'

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
    question_vector = embedder.encode(req.question).tolist()
    results = get_qdrant().search(
        collection_name=COLLECTION, query_vector=question_vector, limit=req.top_k or 5,
        query_filter={"must": [{"key": "doc_type", "match": {"value": "commissioning"}}]},
        with_payload=True
    )
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
        yield f'\n\n__META__{json.dumps({"test_status": status})}__SOURCES__{json.dumps(sources)}'

    return StreamingResponse(generate(), media_type="text/plain")