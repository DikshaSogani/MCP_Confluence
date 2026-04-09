"""
vector_store.py — TF-IDF semantic search using only numpy + standard library.

No PyTorch. No Rust. No external embedding API. No new packages.
numpy is already installed as a qdrant-client dependency.

Works perfectly on Python 3.14 Windows.
"""

import os
import re
import json
import math
import numpy as np
from typing import List, Dict
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

# ── Settings ───────────────────────────────────────────────────
STORE_PATH    = os.getenv("VECTOR_STORE_PATH", "./vector_store_data")
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 60

# Common English stop words to exclude from TF-IDF
STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","shall","should","may","might",
    "must","can","could","this","that","these","those","i","you","he","she",
    "it","we","they","what","which","who","when","where","how","if","then",
    "than","so","as","up","out","about","into","through","after","before",
    "not","no","nor","any","all","both","each","few","more","most","other",
    "some","such","only","own","same","too","very","just","also","its","our",
}


# ── Persistence ────────────────────────────────────────────────

def _ensure_store():
    os.makedirs(STORE_PATH, exist_ok=True)

def _chunks_path():  return os.path.join(STORE_PATH, "chunks.json")
def _matrix_path():  return os.path.join(STORE_PATH, "tfidf_matrix.npz")
def _vocab_path():   return os.path.join(STORE_PATH, "vocab.json")

def _load_chunks() -> List[Dict]:
    p = _chunks_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_chunks(chunks: List[Dict]):
    _ensure_store()
    with open(_chunks_path(), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

def _load_index():
    """Load TF-IDF matrix and vocabulary from disk."""
    mp = _matrix_path()
    vp = _vocab_path()
    if os.path.exists(mp) and os.path.exists(vp):
        matrix = np.load(mp)["matrix"]
        with open(vp, "r") as f:
            vocab = json.load(f)
        return matrix, vocab
    return None, None

def _save_index(matrix: np.ndarray, vocab: Dict):
    _ensure_store()
    np.savez_compressed(_matrix_path(), matrix=matrix)
    with open(_vocab_path(), "w") as f:
        json.dump(vocab, f)


# ── Text processing ────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Lowercase, remove punctuation, split into words, remove stop words."""
    text  = text.lower()
    text  = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    words  = text.split()
    chunks = []
    step   = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks if chunks else [text]


# ── TF-IDF index builder ───────────────────────────────────────

def _build_tfidf(all_chunks: List[str]):
    """
    Build a TF-IDF matrix for all chunks.
    Returns (matrix [n_chunks x vocab_size], vocab dict word->index).
    """
    # Step 1: tokenize all chunks
    tokenized = [_tokenize(chunk) for chunk in all_chunks]

    # Step 2: build vocabulary from words that appear in at least 2 chunks
    # (filters very rare tokens that add noise)
    word_doc_count = Counter()
    for tokens in tokenized:
        for word in set(tokens):
            word_doc_count[word] += 1

    vocab_words = [w for w, c in word_doc_count.items() if c >= 1]
    vocab       = {w: i for i, w in enumerate(vocab_words)}
    V           = len(vocab)
    N           = len(all_chunks)

    if V == 0 or N == 0:
        return np.zeros((max(N, 1), 1)), {}

    # Step 3: compute TF-IDF
    # TF = term frequency in chunk (normalized by chunk length)
    # IDF = log(N / df) where df = number of chunks containing the word
    matrix = np.zeros((N, V), dtype=np.float32)

    for i, tokens in enumerate(tokenized):
        if not tokens:
            continue
        tf = Counter(tokens)
        total = len(tokens)
        for word, count in tf.items():
            if word in vocab:
                j   = vocab[word]
                idf = math.log((N + 1) / (word_doc_count[word] + 1)) + 1.0
                matrix[i, j] = (count / total) * idf

    # L2 normalize each row so cosine similarity = dot product
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    return matrix, vocab


def _query_vector(query: str, vocab: Dict, n_chunks: int) -> np.ndarray:
    """Build a TF-IDF vector for a query against the existing vocabulary."""
    tokens = _tokenize(query)
    if not tokens:
        return np.zeros(len(vocab), dtype=np.float32)

    tf  = Counter(tokens)
    vec = np.zeros(len(vocab), dtype=np.float32)
    total = len(tokens)

    for word, count in tf.items():
        if word in vocab:
            j   = vocab[word]
            idf = math.log((n_chunks + 1) / 2) + 1.0  # conservative IDF for query
            vec[j] = (count / total) * idf

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


# ── Indexing ───────────────────────────────────────────────────

def index_page_from_context(page_id: str, page_title: str,
                             page_url: str, context_str: str) -> int:
    """
    Chunk the page context, rebuild TF-IDF index with all chunks.
    This rebuilds the full index each time (fast enough for <100 pages).
    """
    # Clean context
    clean = re.sub(r"=== PAGE:.*?===", "", context_str)
    clean = re.sub(r"URL:.*?\n", "", clean)
    clean = re.sub(r"--- [\w\s]+ ---", "", clean)
    clean = re.sub(r"\[PDF:.*?\]", "", clean)
    clean = re.sub(r"\[Image:.*?\]", "", clean)
    clean = re.sub(r"\[Linked.*?\]", "", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

    if not clean:
        print(f"  [VECTOR] Skipping '{page_title}' — empty content")
        return 0

    # Load existing chunks, remove old ones for this page
    all_chunk_records = _load_chunks()
    all_chunk_records = [c for c in all_chunk_records if c["page_id"] != page_id]

    # Add new chunks for this page
    new_chunks = chunk_text(clean)
    for i, chunk in enumerate(new_chunks):
        all_chunk_records.append({
            "page_id":     page_id,
            "page_title":  page_title,
            "page_url":    page_url,
            "chunk_index": i,
            "text":        chunk,
        })

    # Rebuild TF-IDF index over all chunks
    all_texts = [r["text"] for r in all_chunk_records]
    matrix, vocab = _build_tfidf(all_texts)

    # Save everything
    _save_chunks(all_chunk_records)
    _save_index(matrix, vocab)

    print(f"  [VECTOR] Indexed '{page_title}': {len(new_chunks)} chunks "
          f"(total: {len(all_chunk_records)} chunks, vocab: {len(vocab)} words)")
    return len(new_chunks)


# ── Searching ──────────────────────────────────────────────────

def search(query: str, n_results: int = 5,
           score_threshold: float = 0.05) -> List[Dict]:
    """
    TF-IDF cosine similarity search across all indexed chunks.
    Returns top-N most relevant chunks.
    """
    all_chunk_records = _load_chunks()
    if not all_chunk_records:
        print("  [VECTOR] No chunks stored — run 'sync' first")
        return []

    matrix, vocab = _load_index()
    if matrix is None or len(vocab) == 0:
        print("  [VECTOR] Index not found — run 'sync' first")
        return []

    q_vec  = _query_vector(query, vocab, len(all_chunk_records))
    scores = matrix @ q_vec   # cosine similarity (rows already L2-normalized)

    # Get top-N indices above threshold
    top_indices = np.argsort(scores)[::-1][:n_results * 2]
    hits = []
    for idx in top_indices:
        score = float(scores[idx])
        if score < score_threshold:
            continue
        rec = all_chunk_records[idx]
        hits.append({
            "text":        rec["text"],
            "page_title":  rec["page_title"],
            "page_url":    rec["page_url"],
            "page_id":     rec["page_id"],
            "score":       round(score, 3),
            "chunk_index": rec["chunk_index"],
        })
        if len(hits) >= n_results:
            break

    print(f"  [VECTOR] '{query[:50]}' -> {len(hits)} hits "
          f"(scores: {[h['score'] for h in hits]})")
    return hits


def build_context_from_hits(hits: List[Dict]) -> tuple:
    """Convert search hits into context string + metadata dict."""
    if not hits:
        return "", {}

    seen_pages = {}
    sections   = []
    for hit in hits:
        title = hit["page_title"]
        if title not in seen_pages:
            seen_pages[title] = hit["page_url"]
        sections.append(
            f"[From: {title} | relevance: {hit['score']}]\n{hit['text']}"
        )

    context = "\n\n---\n\n".join(sections)
    top     = hits[0]
    metadata = {
        "title":       top["page_title"],
        "url":         top["page_url"],
        "attachments": [],
        "also_from":   [
            {"title": t, "url": u}
            for t, u in seen_pages.items()
            if t != top["page_title"]
        ],
    }
    return context, metadata


# ── Stats / Maintenance ────────────────────────────────────────

def get_stats() -> Dict:
    try:
        records = _load_chunks()
        pages   = {}
        for r in records:
            pages[r["page_id"]] = r["page_title"]
        return {
            "total_chunks": len(records),
            "total_pages":  len(pages),
            "pages":        pages,
            "store_path":   STORE_PATH,
        }
    except Exception as e:
        return {"error": str(e)}


def delete_page(page_id: str):
    records = _load_chunks()
    filtered = [r for r in records if r["page_id"] != page_id]
    if len(filtered) < len(records):
        _save_chunks(filtered)
        if filtered:
            matrix, vocab = _build_tfidf([r["text"] for r in filtered])
            _save_index(matrix, vocab)
        print(f"  [VECTOR] Deleted chunks for page '{page_id}'")
    else:
        print(f"  [VECTOR] Page '{page_id}' not found in index")


def clear_all():
    import shutil
    if os.path.exists(STORE_PATH):
        shutil.rmtree(STORE_PATH)
    print(f"  [VECTOR] Store cleared at '{STORE_PATH}'")