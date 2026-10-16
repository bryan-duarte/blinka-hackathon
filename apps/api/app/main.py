from fastapi import FastAPI

app = FastAPI(title="Blinka Hackathon API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
