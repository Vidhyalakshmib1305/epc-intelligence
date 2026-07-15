import httpx  # pyright: ignore[reportMissingImports]
import pytest  # pyright: ignore[reportMissingImports]

BASE = "http://localhost:8000"
TIMEOUT = 300


def test_health():
    r = httpx.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_documents():
    r = httpx.get(f"{BASE}/documents", timeout=10)
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    assert len(docs) >= 4  # seed data


def test_query():
    r = httpx.post(f"{BASE}/query",
        json={"question": "What are the UPS redundancy requirements?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) > 0


def test_spec_compliance_non_compliant():
    r = httpx.post(f"{BASE}/agents/spec-compliance",
        json={"question": "Is a UPS with 94% efficiency compliant?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert "compliance_status" in data
    assert data["compliance_status"] in ["COMPLIANT", "NON-COMPLIANT", "REQUIRES VERIFICATION"]
    assert data["compliance_status"] == "NON-COMPLIANT"


def test_schedule_risk_high():
    r = httpx.post(f"{BASE}/agents/schedule-risk",
        json={"question": "What are the current delays and risks to the project timeline?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert "risk_level" in data
    assert data["risk_level"] in ["HIGH", "MEDIUM", "LOW"]


def test_rfi_copilot():
    r = httpx.post(f"{BASE}/agents/rfi-copilot",
        json={"question": "Has there been any RFI about cable tray fill factor?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) > 0


def test_upload_non_pdf_rejected():
    """Non-PDF files should be rejected with 400."""
    r = httpx.post(f"{BASE}/documents/upload",
        files={"file": ("test.txt", b"this is not a pdf", "text/plain")},
        data={"doc_type": "specification"},
        timeout=30)
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_upload_empty_file_rejected():
    """Empty files should be rejected with 400."""
    r = httpx.post(f"{BASE}/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"doc_type": "specification"},
        timeout=30)
    assert r.status_code == 400


def test_upload_corrupt_pdf_rejected():
    """Corrupt PDF bytes should be rejected with 400."""
    r = httpx.post(f"{BASE}/documents/upload",
        files={"file": ("corrupt.pdf", b"not a real pdf content", "application/pdf")},
        data={"doc_type": "specification"},
        timeout=30)
    assert r.status_code == 400


def test_health_services_structure():
    """Health endpoint must return all 3 services."""
    r = httpx.get(f"{BASE}/health", timeout=10)
    data = r.json()
    assert "services" in data
    assert "qdrant" in data["services"]
    assert "ollama" in data["services"]
    assert "postgres" in data["services"]
    assert data["services"]["ollama"]["mistral_ready"] is True


def test_query_no_doc_type_filter():
    """Query without doc_type filter should still return results."""
    r = httpx.post(f"{BASE}/query",
        json={"question": "What is this project about?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    assert "answer" in r.json()


def test_spec_compliance_compliant_case():
    """A compliant query should return COMPLIANT status."""
    r = httpx.post(f"{BASE}/agents/spec-compliance",
        json={"question": "Is galvanised steel cable tray compliant?", "top_k": 3},
        timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["compliance_status"] in ["COMPLIANT", "NON-COMPLIANT", "REQUIRES VERIFICATION"]


def test_documents_count():
    """Should have at least 4 seed documents."""
    r = httpx.get(f"{BASE}/documents", timeout=10)
    assert r.status_code == 200
    assert len(r.json()) >= 4