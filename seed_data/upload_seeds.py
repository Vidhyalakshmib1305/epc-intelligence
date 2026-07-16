import httpx  # pyright: ignore[reportMissingImports]
import io
import os
from fpdf import FPDF  # pyright: ignore[reportMissingModuleSource]
from fpdf.enums import XPos, YPos  # pyright: ignore[reportMissingModuleSource]

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

def upload(filename, doc_type):
    pdf_name = filename.replace(".txt", ".pdf")

    if filename.endswith(".txt"):
        pdf_file = txt_to_pdf_bytes(os.path.join(DOCS_DIR, filename))
    else:
        with open(os.path.join(os.path.dirname(__file__), filename), "rb") as f:
            pdf_file = io.BytesIO(f.read())

    with httpx.Client() as client:
        r = client.post(
            f"{API_URL}/documents/upload",
            data={"doc_type": doc_type},
            files={"file": (pdf_name, pdf_file, "application/pdf")},
            timeout=60
        )
        if r.status_code >= 400:
            print(f"{pdf_name}: ERROR {r.status_code} | {r.text[:500]}")
            return
        data = r.json()
        print(f"{pdf_name}: {r.status_code} | chunks={data.get('chunks_stored','?')} | pages={data.get('page_count','?')}")

for filename, doc_type in doc_configs:
    upload(filename, doc_type)

upload("supply_chain.pdf", "supply_chain")