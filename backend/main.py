from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
import os
import sys
import uuid
import shutil
import mimetypes
import traceback

from database import SessionLocal, Employee, Certification, SystemSettings, init_db, UPLOAD_DIR
from seed_data import populate_initial_data
from scheduler import start_scheduler, get_full_report_data
from mailer import send_alert_email, send_weekly_excel_report
from excel_generator import generate_safety_excel_report

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
    employees_data, _, _ = get_full_report_data(db)
    result = []
    for emp in employees_data:
        exp_c = sum(1 for c in emp["certifications"] if c["status"] == "expired")
        warn_c = sum(1 for c in emp["certifications"] if c["status"] == "warning")
        result.append({
            **emp,
            "expired_count": exp_c,
            "warning_count": warn_c
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
        certs = db.query(Certification).filter(Certification.employee_id == emp_id).all()
        for c in certs:
            if c.file_name:
                fpath = os.path.join(UPLOAD_DIR, c.file_name)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
        db.query(Certification).filter(Certification.employee_id == emp_id).delete()
        db.delete(emp)
        db.commit()
    return {"status": "ok"}

@app.post("/api/certifications")
def save_certification(
    id: Optional[int] = Form(None),
    employee_id: int = Form(...),
    category: str = Form(...),
    course_name: str = Form(...),
    pass_date: Optional[str] = Form(None),
    valid_until: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    p_date = None
    if pass_date and pass_date.strip() not in ["-", ""]:
        p_date = datetime.strptime(pass_date.strip(), "%d.%m.%Y").date()
    
    v_date = None
    if valid_until and valid_until.strip() not in ["-", ""]:
        v_date = datetime.strptime(valid_until.strip(), "%d.%m.%Y").date()

    saved_file_name = None
    orig_file_name = None

    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        saved_file_name = f"{uuid.uuid4().hex}{ext}"
        orig_file_name = file.filename
        file_path = os.path.join(UPLOAD_DIR, saved_file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    if id:
        cert = db.query(Certification).filter(Certification.id == id).first()
        if not cert:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        cert.category = category
        cert.course_name = course_name
        cert.pass_date = p_date
        cert.valid_until = v_date
        if saved_file_name:
            if cert.file_name:
                old_p = os.path.join(UPLOAD_DIR, cert.file_name)
                if os.path.exists(old_p):
                    try:
                        os.remove(old_p)
                    except Exception:
                        pass
            cert.file_name = saved_file_name
            cert.file_display_name = orig_file_name
    else:
        cert = Certification(
            employee_id=employee_id,
            category=category,
            course_name=course_name,
            pass_date=p_date,
            valid_until=v_date,
            file_name=saved_file_name or "",
            file_display_name=orig_file_name or ""
        )
        db.add(cert)
    
    db.commit()
    return {"status": "ok"}

@app.delete("/api/certifications/{cert_id}")
def delete_cert(cert_id: int, db: Session = Depends(get_db)):
    c = db.query(Certification).filter(Certification.id == cert_id).first()
    if c:
        if c.file_name:
            p = os.path.join(UPLOAD_DIR, c.file_name)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        db.delete(c)
        db.commit()
    return {"status": "ok"}

@app.delete("/api/certifications/{cert_id}/file")
def delete_cert_file(cert_id: int, db: Session = Depends(get_db)):
    c = db.query(Certification).filter(Certification.id == cert_id).first()
    if c and c.file_name:
        p = os.path.join(UPLOAD_DIR, c.file_name)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
        c.file_name = ""
        c.file_display_name = ""
        db.commit()
    return {"status": "ok"}

@app.get("/api/files/{filename}")
def get_file(filename: str):
    fpath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Файл не найден")
    mime, _ = mimetypes.guess_type(fpath)
    return FileResponse(
        fpath,
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@app.get("/api/reports/excel")
def download_excel_report(db: Session = Depends(get_db)):
    employees_data, _, _ = get_full_report_data(db)
    excel_bytes = generate_safety_excel_report(employees_data)
    today_str = date.today().strftime("%d_%m_%Y")
    filename = f"TMK_Reestr_Obucheniya_{today_str}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.post("/api/reports/send-weekly-now")
def send_weekly_report_now(db: Session = Depends(get_db)):
    try:
        settings = db.query(SystemSettings).first()
        if not settings or not settings.smtp_user or not settings.smtp_pass:
            return {"success": False, "message": "Сначала сохраните настройки SMTP (логин и пароль приложения)!"}
        
        recipient = settings.safety_officer_email or settings.smtp_user
        employees_data, stats, urgent_items = get_full_report_data(db)
        excel_bytes = generate_safety_excel_report(employees_data)
        today_str = date.today().strftime("%d_%m_%Y")
        filename = f"TMK_Reestr_Obucheniya_{today_str}.xlsx"

        success, msg = send_weekly_excel_report(
            settings=settings,
            recipient_email=recipient,
            excel_bytes=excel_bytes,
            filename=filename,
            stats=stats,
            urgent_items=urgent_items
        )
        return {"success": success, "message": msg}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"Ошибка сервера: {str(e)}"}

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
    try:
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
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"Ошибка сервера: {str(e)}"}

if getattr(sys, 'frozen', False):
    frontend_dir = os.path.join(sys._MEIPASS, "frontend")
else:
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

if not os.path.exists(frontend_dir):
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_dir, "index.html")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
