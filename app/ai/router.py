from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.schemas import AskRequest, AskResponse, DocumentOut
from app.api.deps import require_roles
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.db.session import get_db
from app.models import Document, Role, User
from app.schemas.common import Page, PageParams, make_page
from app.services.pagination import paginate

router = APIRouter(prefix="/assistant", tags=["AI Learning Assistant (optional)"])
student_only = require_roles(Role.student)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_notes(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(student_only)):
    """Upload a PDF of notes. Text is extracted, chunked and stored for retrieval."""
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = file.file.read(limit + 1)  # read at most limit+1 bytes -> reject oversized files cheaply
    if len(data) > limit:
        raise BadRequestError(f"File too large (max {settings.MAX_UPLOAD_MB} MB)")
    return service.ingest_pdf(db, user, file.filename or "notes.pdf", data)


@router.get("/documents", response_model=Page[DocumentOut])
def list_documents(params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(student_only)):
    items, total = paginate(db, select(Document).where(Document.owner_id == user.id).order_by(Document.uploaded_at.desc()), params)
    return make_page(items, total, params)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    db.delete(service.get_own_document(db, doc_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{doc_id}/ask", response_model=AskResponse)
def ask_question(doc_id: int, body: AskRequest, db: Session = Depends(get_db), user: User = Depends(student_only)):
    return service.ask(db, doc_id, user, body.question, body.top_k)
