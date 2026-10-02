from fastapi import FastAPI

app = FastAPI(title="HR Policy Intelligence Agent")


@app.get("/health")
def health():
    return {"status": "ok"}