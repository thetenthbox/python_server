"""
Database models for GPU Job Queue Server
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"
    
    job_id = Column(String, primary_key=True)
    competition_id = Column(String, nullable=False)
    project_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    expected_time = Column(Integer, nullable=False)  # seconds
    token_hash = Column(String, nullable=False)
    status = Column(String, nullable=False)  # pending, running, completed, failed, cancelled
    node_id = Column(Integer, nullable=True)  # 0-7, NULL if pending
    code_path = Column(String, nullable=True)
    yaml_path = Column(String, nullable=True)
    remote_pid = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class NodeState(Base):
    __tablename__ = "node_state"
    
    node_id = Column(Integer, primary_key=True)
    current_job_id = Column(String, nullable=True)
    total_queue_time = Column(Integer, default=0)
    is_busy = Column(Boolean, default=False)


class Token(Base):
    __tablename__ = "tokens"
    
    token_hash = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Admin tokens have special privileges


# Database setup
engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables"""
    Base.metadata.create_all(bind=engine)
    
    # Initialize node states if not exists
    db = SessionLocal()
    try:
        for i in range(8):
            node = db.query(NodeState).filter(NodeState.node_id == i).first()
            if not node:
                node = NodeState(node_id=i, total_queue_time=0, is_busy=False)
                db.add(node)
        db.commit()
    finally:
        db.close()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

