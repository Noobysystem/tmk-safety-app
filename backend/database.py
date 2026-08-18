from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = "sqlite:///./safety_training.db"

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

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True)
    smtp_host = Column(String, default="smtp.yandex.ru")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String, default="")
    smtp_pass = Column(String, default="")
    sender_email = Column(String, default="safety@company.ru")
    safety_officer_email = Column(String, default="")
    notify_days = Column(String, default="30,14,3")

def init_db():
    Base.metadata.create_all(bind=engine)
