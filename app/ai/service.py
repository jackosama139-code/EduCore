import io
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.retrieval import chunk_text, rank_chunks
from app.ai.schemas import AskResponse, Source
from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models import Document, DocumentChunk, User

log = logging.getLogger("educore.ai")


def extract_pdf_text(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except (PyPdfError, ValueError, KeyError) as exc:
        raise BadRequestError("Could not read this PDF (corrupt or encrypted)") from exc
    return "\n".join(pages), len(pages)


def ingest_pdf(db: Session, user: User, filename: str, data: bytes) -> Document:
    if not data.startswith(b"%PDF"):
        raise BadRequestError("File is not a valid PDF")
    text, pages = extract_pdf_text(data)
    chunks = chunk_text(text)
    if not chunks:
        raise BadRequestError("No extractable text found (scanned/image-only PDFs are not supported)")
    doc = Document(owner_id=user.id, filename=filename[:255], num_pages=pages, num_chunks=len(chunks))
    doc.chunks = [DocumentChunk(chunk_index=i, text=c) for i, c in enumerate(chunks)]
    db.add(doc)
    db.commit()
    return doc


def get_own_document(db: Session, doc_id: int, user: User) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.owner_id != user.id:  # 404 for other people's documents, too
        raise NotFoundError("Document not found")
    return doc


def ask(db: Session, doc_id: int, user: User, question: str, top_k: int) -> AskResponse:
    doc = get_own_document(db, doc_id, user)
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index)))
    ranked = rank_chunks(question, [c.text for c in chunks], top_k=top_k)
    if not ranked:
        return AskResponse(answer="I couldn't find anything relevant to that question in your notes.", mode="extractive", sources=[])
    sources = [Source(chunk_index=chunks[i].chunk_index, score=round(s, 3), text=chunks[i].text) for i, s in ranked]

    if llm.llm_available():
        try:
            return AskResponse(answer=llm.generate_answer(question, [s.text for s in sources]), mode="llm", sources=sources)
        except Exception:  # network/quota/etc: degrade gracefully instead of failing the request
            log.exception("LLM call failed; falling back to extractive answer")
    best = sources[0].text
    return AskResponse(answer=f"Most relevant passage from your notes:\n\n{best}", mode="extractive", sources=sources)
