import httpx
import io
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

API_URL  = "http://localhost:8000"
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")

doc_configs = [
    ("spec_electrical.txt",  "specification"),
    ("spec_cooling.txt",     "specification"),
    ("project_schedule.txt", "schedule"),
    ("rfi_log.txt",          "rfi"),
]

def txt_to_pdf_bytes(filepath):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            pdf.cell(0, 4, line.rstrip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return io.BytesIO(bytes(pdf.output()))

for filename, doc_type in doc_configs:
    filepath = os.path.join(DOCS_DIR, filename)
    pdf_name = filename.replace(".txt", ".pdf")
    pdf_file = txt_to_pdf_bytes(filepath)

    with httpx.Client() as client:
        r = client.post(
            f"{API_URL}/documents/upload",
            params={"doc_type": doc_type},
            files={"file": (pdf_name, pdf_file, "application/pdf")},
            timeout=60
        )
        data = r.json()
        print(f"{pdf_name}: {r.status_code} | chunks={data.get('chunks_stored','?')} | pages={data.get('page_count','?')}")