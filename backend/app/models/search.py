from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.base_class import Base

class Search(Base):
    __tablename__ = "search"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)
    tribunal = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SearchResult(Base):
    __tablename__ = "search_result"
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("search.id"))
    content = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class News(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("search.id"))
    title = Column(String)
    url = Column(String, unique=True, index=True)
    source = Column(String)
    author = Column(String, nullable=True)
    snippet = Column(String)
    image_url = Column(String, nullable=True)
    published_date = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    correlation = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Comment(Base):
    __tablename__ = "comment"
    id = Column(Integer, primary_key=True, index=True)
    news_id = Column(Integer, ForeignKey("news.id"), index=True)
    author = Column(String, default="Anônimo")
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
