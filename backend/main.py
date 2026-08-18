from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
import os

from database import SessionLocal, Employee, Certification, SystemSettings, init_db
from seed_data import populate_initial_data
from scheduler import start_scheduler
from mailer import send_alert_email

app = FastAPI(title="TMK Safety & Training Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class EmployeeSchema(BaseModel):
    id: Optional[int] = None
    full_name: str
    position: Optional[str] = ""
    department: Optional[str] = ""
    email: Optional[str] = ""

class CertSchema(BaseModel):
    id: Optional[int] = None
    employee_id: int
    category: str
    course_name: str
    pass_date: Optional[str] = None
    valid_until: Optional[str] = None
    notes: Optional[str] = ""

class SettingsSchema(BaseModel):
    smtp_host: Optional[str] = "smtp.yandex.ru"
    smtp_port: Optional[int] = 465
    smtp_user: Optional[str] = ""
    smtp_pass: Optional[str] = ""
    sender_email: Optional[str] = ""
    safety_officer_email: Optional[str] = ""
    notify_days: Optional[str] = "30,14,3"

@app.on_event("startup")
def on_startup():
    init_db()
    populate_initial_data()
    start_scheduler()

@app.get("/api/employees")
def list_employees(db: Session = Depends(get_db)):
    employees = db.query(Employee).all()
    today = date.today()
    result = []
    
    for emp in employees:
        certs = db.query(Certification).filter(Certification.employee_id == emp.id).all()
        expired_count = 0
        warning_count = 0
        
        cert_list = []
        for c in certs:
            days_left = None
            status = "valid"
            if c.valid_until:
                days_left = (c.valid_until - today).days
                if days_left < 0:
                    status = "expired"
                    expired_count += 1
                elif days_left <= 30:
                    status = "warning"
                    warning_count += 1
            else:
                status = "permanent"

            cert_list.append({
                "id": c.id,
                "category": c.category,
                "course_name": c.course_name,
                "pass_date": c.pass_date.strftime("%d.%m.%Y") if c.pass_date else "-",
                "valid_until": c.valid_until.strftime("%d.%m.%Y") if c.valid_until else "-",
                "days_left": days_left,
                "status": status
            })

        result.append({
            "id": emp.id,
            "full_name": emp.full_name,
            "position": emp.position,
            "department": emp.department,
            "email": emp.email,
            "expired_count": expired_count,
            "warning_count": warning_count,
            "certifications": cert_list
        })
    return result

@app.post("/api/employees")
def save_employee(emp_data: EmployeeSchema, db: Session = Depends(get_db)):
    if emp_data.id:
        emp = db.query(Employee).filter(Employee.id == emp_data.id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        emp.full_name = emp_data.full_name.strip()
        emp.position = emp_data.position.strip()
        emp.department = emp_data.department.strip()
        emp.email = emp_data.email.strip()
    else:
        emp = Employee(
            full_name=emp_data.full_name.strip(),
            position=emp_data.position.strip(),
            department=emp_data.department.strip(),
            email=emp_data.email.strip()
        )
        db.add(emp)
    db.commit()
    return {"status": "ok"}

@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if emp:
        db.query(Certification).filter(Certification.employee_id == emp_id).delete()
        db.delete(emp)
        db.commit()
    return {"status": "ok"}

@app.post("/api/certifications")
def save_certification(cert_data: CertSchema, db: Session = Depends(get_db)):
    p_date = None
    if cert_data.pass_date and cert_data.pass_date.strip() not in ["-", ""]:
        p_date = datetime.strptime(cert_data.pass_date.strip(), "%d.%m.%Y").date()
    
    v_date = None
    if cert_data.valid_until and cert_data.valid_until.strip() not in ["-", ""]:
        v_date = datetime.strptime(cert_data.valid_until.strip(), "%d.%m.%Y").date()

    if cert_data.id:
        cert = db.query(Certification).filter(Certification.id == cert_data.id).first()
        if not cert:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        cert.category = cert_data.category
        cert.course_name = cert_data.course_name
        cert.pass_date = p_date
        cert.valid_until = v_date
    else:
        cert = Certification(
            employee_id=cert_data.employee_id,
            category=cert_data.category,
            course_name=cert_data.course_name,
            pass_date=p_date,
            valid_until=v_date
        )
        db.add(cert)
    
    db.commit()
    return {"status": "ok"}

@app.delete("/api/certifications/{cert_id}")
def delete_cert(cert_id: int, db: Session = Depends(get_db)):
    c = db.query(Certification).filter(Certification.id == cert_id).first()
    if c:
        db.delete(c)
        db.commit()
    return {"status": "ok"}

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    s = db.query(SystemSettings).first()
    return s

@app.post("/api/settings")
def update_settings(data: SettingsSchema, db: Session = Depends(get_db)):
    s = db.query(SystemSettings).first()
    if not s:
        s = SystemSettings()
        db.add(s)
    s.smtp_host = (data.smtp_host or "smtp.yandex.ru").strip()
    s.smtp_port = int(data.smtp_port or 465)
    s.smtp_user = (data.smtp_user or "").strip()
    s.smtp_pass = (data.smtp_pass or "").strip().replace(" ", "")
    s.sender_email = (data.sender_email or s.smtp_user).strip()
    s.safety_officer_email = (data.safety_officer_email or s.smtp_user).strip()
    s.notify_days = (data.notify_days or "30,14,3").strip()
    db.commit()
    return {"status": "ok"}

@app.post("/api/settings/test-email")
def test_email(test_data: Optional[SettingsSchema] = None, db: Session = Depends(get_db)):
    s = db.query(SystemSettings).first()
    if not s:
        s = SystemSettings()
        db.add(s)

    if test_data:
        s.smtp_host = (test_data.smtp_host or "smtp.yandex.ru").strip()
        s.smtp_port = int(test_data.smtp_port or 465)
        s.smtp_user = (test_data.smtp_user or "").strip()
        s.smtp_pass = (test_data.smtp_pass or "").strip().replace(" ", "")
        s.sender_email = (test_data.sender_email or s.smtp_user).strip()
        s.safety_officer_email = (test_data.safety_officer_email or s.smtp_user).strip()
        s.notify_days = (test_data.notify_days or "30,14,3").strip()
        db.commit()

    cfg = s
    recipient = cfg.safety_officer_email if cfg.safety_officer_email else cfg.smtp_user
    success, msg = send_alert_email(
        settings=cfg,
        recipient_email=recipient,
        subject="🧪 Тестовое оповещение из системы обучения ТМК",
        items=[{
            "employee_name": "Чемезов Н. А.",
            "category": "Охрана труда",
            "course_name": "Проверка системы email-напоминаний",
            "valid_until": "17.02.2027",
            "days_left": 30
        }]
    )
    return {"success": success, "message": msg}

static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if not os.path.exists(static_path):
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))

if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="frontend")
