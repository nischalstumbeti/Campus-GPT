"""Document model for knowledge base."""
from sqlalchemy import Column, String, DateTime, Integer, Text
from datetime import datetime

from app.utils.database import Base


class Document(Base):
    """Uploaded document metadata."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="processing")  # processing, completed, failed
    uploaded_by = Column(Integer)  # user id
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(Text)  # Additional metadata
