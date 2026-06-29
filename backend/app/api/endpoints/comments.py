from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.models.search import Comment, News

router = APIRouter()

class CommentCreate(BaseModel):
    news_id: int
    author: str = "Anônimo"
    content: str

class CommentResponse(BaseModel):
    id: int
    news_id: int
    author: str
    content: str
    created_at: str

@router.post("/comments")
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == comment.news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    if not comment.content or len(comment.content.strip()) < 2:
        raise HTTPException(status_code=400, detail="Comentário deve ter pelo menos 2 caracteres")
    if len(comment.content) > 1000:
        raise HTTPException(status_code=400, detail="Comentário muito longo (máx 1000 caracteres)")
    if not comment.author or not comment.author.strip():
        comment.author = "Anônimo"
    db_comment = Comment(
        news_id=comment.news_id,
        author=comment.author.strip()[:50],
        content=comment.content.strip()
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return {
        "id": db_comment.id,
        "news_id": db_comment.news_id,
        "author": db_comment.author,
        "content": db_comment.content,
        "created_at": db_comment.created_at.isoformat() if db_comment.created_at else ""
    }

@router.get("/comments/{news_id}")
def list_comments(news_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(
        Comment.news_id == news_id
    ).order_by(Comment.created_at.desc()).limit(50).all()
    return [{
        "id": c.id,
        "news_id": c.news_id,
        "author": c.author,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else ""
    } for c in comments]
