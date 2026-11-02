from fastapi.testclient import TestClient

from app.ai.retrieval import chunk_text, rank_chunks, tokenize
from tests.conftest import auth

URL = "/api/v1/assistant"


def make_pdf(text: str) -> bytes:
    """Build a tiny valid one-page PDF so tests need no extra libraries."""
    stream = f"BT /F1 10 Tf 20 700 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 5000 800] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


NOTES = ("Photosynthesis converts light energy into chemical energy inside chloroplasts. " * 20 +
         "Binary search runs in logarithmic time because it halves the sorted array each step. " * 20 +
         "The mitochondria is the powerhouse of the cell producing ATP. " * 20)


# ---- unit tests for retrieval (no HTTP) ----
def test_tokenize_drops_stopwords():
    assert tokenize("What is the Time Complexity of binary search?") == ["time", "complexity", "binary", "search"]


def test_chunking_overlap_and_coverage():
    words = [f"w{i}" for i in range(400)]
    chunks = chunk_text(" ".join(words), words_per_chunk=100, overlap=20)
    assert chunks[0].split()[-20:] == chunks[1].split()[:20]
    assert "w399" in chunks[-1]


def test_ranking_prefers_relevant_chunk():
    chunks = ["cats and dogs are pets", "binary search halves a sorted array", "the sky is blue"]
    best = rank_chunks("how does binary search work", chunks, top_k=2)
    assert best[0][0] == 1 and all(i != 2 for i, _ in best)
    assert rank_chunks("quantum entanglement", chunks) == []


# ---- API tests ----
def test_upload_and_ask_extractive_without_api_key(client, stu1):
    u, _ = stu1
    r = client.post(f"{URL}/documents", files={"file": ("notes.pdf", make_pdf(NOTES), "application/pdf")}, headers=auth(u))
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["num_chunks"] >= 2
    a = client.post(f"{URL}/documents/{doc['id']}/ask", json={"question": "How fast is binary search?"}, headers=auth(u))
    assert a.status_code == 200
    body = a.json()
    assert body["mode"] == "extractive" and "logarithmic" in body["answer"] and body["sources"]


def test_non_pdf_rejected_and_other_students_documents_hidden(client, stu1, stu2):
    assert client.post(f"{URL}/documents", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}, headers=auth(stu1[0])).status_code == 400
    doc = client.post(f"{URL}/documents", files={"file": ("n.pdf", make_pdf(NOTES), "application/pdf")}, headers=auth(stu1[0])).json()
    assert client.post(f"{URL}/documents/{doc['id']}/ask", json={"question": "binary search?"}, headers=auth(stu2[0])).status_code == 404
    assert client.delete(f"{URL}/documents/{doc['id']}", headers=auth(stu2[0])).status_code == 404
    assert client.get(f"{URL}/documents", headers=auth(stu2[0])).json()["total"] == 0
    assert client.get(f"{URL}/documents", headers=auth(stu1[0])).json()["total"] == 1


def test_assistant_is_student_only(client, faculty):
    assert client.get(f"{URL}/documents", headers=auth(faculty)).status_code == 403


def test_llm_failure_falls_back_to_extractive(client, stu1, monkeypatch):
    from app.ai import llm
    from app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(llm, "generate_answer", lambda q, p: (_ for _ in ()).throw(RuntimeError("API down")))
    u, _ = stu1
    doc = client.post(f"{URL}/documents", files={"file": ("n.pdf", make_pdf(NOTES), "application/pdf")}, headers=auth(u)).json()
    a = client.post(f"{URL}/documents/{doc['id']}/ask", json={"question": "What is photosynthesis?"}, headers=auth(u)).json()
    assert a["mode"] == "extractive"


def test_llm_mode_when_key_present(client, stu1, monkeypatch):
    from app.ai import llm
    from app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(llm, "generate_answer", lambda q, p: "LLM says: it halves the array.")
    u, _ = stu1
    doc = client.post(f"{URL}/documents", files={"file": ("n.pdf", make_pdf(NOTES), "application/pdf")}, headers=auth(u)).json()
    a = client.post(f"{URL}/documents/{doc['id']}/ask", json={"question": "binary search"}, headers=auth(u)).json()
    assert a["mode"] == "llm" and a["answer"].startswith("LLM says")


def test_module_absent_when_disabled(monkeypatch):
    from app.core.config import settings
    from app.main import create_app
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    c = TestClient(create_app())
    assert c.get(f"{URL}/documents").status_code == 404
    assert c.get("/health").json() == {"status": "ok"}
