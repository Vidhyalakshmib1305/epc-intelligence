from fastapi import FastAPI

app = FastAPI(title="EPC Intelligence API")

@app.get("/health")
def health():
    return {"status": "ok"}