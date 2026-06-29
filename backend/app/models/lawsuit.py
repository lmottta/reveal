from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base

class Lawsuit(Base):
    __tablename__ = "lawsuit"

    id = Column(Integer, primary_key=True, index=True)
    cnj = Column(String, unique=True, index=True, nullable=False)
    tribunal = Column(String, index=True, nullable=True)
    state = Column(String, nullable=True)        # Estado (UF)
    comarca = Column(String, nullable=True)      # Comarca
    court = Column(String, nullable=True)        # Vara
    judge = Column(String, nullable=True)        # Nome do Juiz(a)
    forum_address = Column(String, nullable=True) # Endereço físico do Fórum
    class_type = Column(String, nullable=True)   # Classe processual
    subject = Column(String, nullable=True)      # Assunto principal
    parties = Column(Text, nullable=True)        # Partes do processo (JSON)
    status = Column(String, nullable=True)       # Situação atual
    distribution_date = Column(String, nullable=True) # Data de distribuição
    last_movement_date = Column(String, nullable=True) # Data da última movimentação
    movements = Column(Text, nullable=True)
    last_update = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
