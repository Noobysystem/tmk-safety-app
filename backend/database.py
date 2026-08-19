import os
import sys
from sqlalchemy import create_engine, Column, Integer, String, Date, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = os.path.join(APP_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "safety_training.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False, unique=True)
    position = Column(String, default="")
    department = Column(String, default="")
    email = Column(String, default="")

class Certification(Base):
    __tablename__ = "certifications"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    pass_date = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True)
    notes = Column(String, default="")
    file_name = Column(String, default="")
    file_display_name = Column(String, default="")

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True)
    smtp_host = Column(String, default="smtp.yandex.ru")
    smtp_port = Column(Integer, default=465)
    smtp_user = Column(String, default="")
    smtp_pass = Column(String, default="")
    sender_email = Column(String, default="safety@company.ru")
    safety_officer_email = Column(String, default="")
    notify_days = Column(String, default="30,14,3")

def init_db():
    Base.metadata.create_all(bind=engine)
    # Мягкая миграция для добавления колонок файлов, если база уже создана
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE certifications ADD COLUMN file_name VARCHAR DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE certifications ADD COLUMN file_display_name VARCHAR DEFAULT ''"))
        except Exception:
            pass
        conn.commit()
