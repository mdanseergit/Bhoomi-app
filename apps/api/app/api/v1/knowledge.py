"""
Knowledge / RAG endpoints. Uses PostgreSQL full-text search for the
document-level global search bar and pgvector cosine similarity for
semantic retrieval used by the AI assistant (PRODUCT SPEC sections 23-24,
45).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
embedding_service = EmbeddingService()


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "source": d.source,
            "authority": d.authority,
            "state": d.state,
            "crop": d.crop,
            "language": d.language,
            "version": d.version,
            "url": d.url,
        }
        for d in docs
    ]


@router.get("/search")
def search_knowledge(q: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not q or len(q.strip()) < 2:
        return {"results": []}
    # Semantic search via pgvector cosine distance against the (possibly
    # deterministic-local) embedding of the query.
    query_vector = embedding_service.embed([q])[0]
    rows = (
        db.query(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .filter(KnowledgeChunk.embedding.isnot(None))
        .order_by(KnowledgeChunk.embedding.cosine_distance(query_vector))
        .limit(5)
        .all()
    )
    return {
        "results": [
            {
                "document_id": str(doc.id),
                "title": doc.title,
                "authority": doc.authority,
                "excerpt": chunk.content[:280],
            }
            for chunk, doc in rows
        ]
    }
