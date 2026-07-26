from orchestrator import run

result = run("where is the request timeout set", top_k=3, should_generate=True)

print("Retrieved:")
for r in result["retrieved"]:
    print(f"  - {r['name']} ({r['file']}) score={r['score']}")

print(f"\nFlagged chunks: {result['flagged_chunks']}")
print(f"\nGenerated answer:\n{result.get('answer')}")
print(f"\nGeneration error (if any):\n{result.get('generation_error')}")