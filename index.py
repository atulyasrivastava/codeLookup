import json
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

CHUNKS_FILE = "chunks.json"
COLLECTION_NAME = "code_chunks"
VECTOR_DB = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
VECTOR_SIZE = 768  # nomic-embed-text outputs 768-dimensional vectors

def get_embedding(text):
    """Send text to Ollama and get back its embedding vector."""
    response = requests.post(OLLAMA_URL, json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]


def main():
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    client = QdrantClient(url=VECTOR_DB)

    # (re)create the collection fresh each time we run this
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )

    points = []
    skipped = []
    for i, chunk in enumerate(chunks):
        # embed the docstring + code together, gives the model more context
        text_to_embed = f"{chunk['name']}\n{chunk['docstring']}\n{chunk['code']}"
        try:
            vector = get_embedding(text_to_embed)
        except Exception as e:
            skipped.append((i, chunk['name'], str(e)))
            continue

        points.append(PointStruct(
            id=i,
            vector=vector,
            payload=chunk  # store name, type, file, code, docstring alongside the vector
        ))

        if (i + 1) % 50 == 0:
            print(f"Embedded {i + 1}/{len(chunks)} chunks...")

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Done. Indexed {len(points)} chunks into Qdrant.")
    if skipped:
        print(f"Skipped {len(skipped)} chunks due to errors:")
        for idx, name, err in skipped:
            print(f"  - chunk {idx} ({name}): {err}")


if __name__ == "__main__":
    main()