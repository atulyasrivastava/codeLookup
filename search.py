import sys
import requests
from qdrant_client import QdrantClient

COLLECTION_NAME = "code_chunks"
VECTOR_DB = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

def get_embedding(text):
    response = requests.post(OLLAMA_URL, json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]


def search(query, top_k=5):
    client = QdrantClient(url=VECTOR_DB)
    query_vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k
    ).points

    print(f"\nTop {top_k} results for: \"{query}\"\n")
    for i, result in enumerate(results):
        payload = result.payload
        print(f"{i+1}. {payload['name']} ({payload['type']}) — score: {result.score:.3f}")
        print(f"   file: {payload['file']}")
        print(f"   {payload['code'][:200]}...")  # first 200 chars, keeps output readable
        print()


if __name__ == "__main__":
    query = " ".join(sys.argv[1:])
    if not query:
        print("Usage: python search.py <your question here>")
        sys.exit(1)
    search(query)