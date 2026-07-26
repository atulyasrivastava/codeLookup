import ast
import json
import os

TARGET_DIR = "target-repo"
OUTPUT_FILE = "chunks.json"

def extract_chunks_from_file(filepath):
    """Read one Python file and pull out every function/class as a chunk."""
    chunks = []
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # skip files that don't parse cleanly, don't waste time debugging these
        return chunks

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            try:
                code_segment = ast.get_source_segment(source, node)
            except Exception:
                continue
            if code_segment is None:
                continue

            chunks.append({
                "name": node.name,
                "type": type(node).__name__,   # FunctionDef, AsyncFunctionDef, or ClassDef
                "file": os.path.relpath(filepath, TARGET_DIR),
                "code": code_segment,
                "docstring": ast.get_docstring(node) or ""
            })

    return chunks


def main():
    all_chunks = []

    for root, dirs, files in os.walk(TARGET_DIR):
        # skip test folders and hidden folders like .git
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "tests"]

        for filename in files:
            if filename.endswith(".py"):
                filepath = os.path.join(root, filename)
                all_chunks.extend(extract_chunks_from_file(filepath))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"Extracted {len(all_chunks)} chunks -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()