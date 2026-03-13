from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Embedding Service")
VECTOR_SIZE = 384


class EmbedRequest(BaseModel):
    text: List[str] | str | None = None
    texts: List[str] | str | None = None

    def normalized_texts(self) -> List[str]:
        source = self.text if self.text is not None else self.texts
        if source is None:
            return []
        if isinstance(source, str):
            return [source]
        return source


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/embed")
def embed(request: EmbedRequest) -> dict[str, List[List[float]]]:
    texts = request.normalized_texts()
    embeddings = [[0.0] * VECTOR_SIZE for _ in texts]
    return {"embeddings": embeddings}
