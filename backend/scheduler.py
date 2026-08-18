from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date
from database import SessionLocal, Employee, Certification, SystemSettings
from mailer import send_alert_email

def check_deadlines_job():
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if not settings or not settings.safety_officer_email:
            return

        notify_days_list = [int(x.strip()) for x in settings.notify_days.split(",") if x.strip().isdigit()]
        today = date.today()

        certs = db.query(Certification).filter(Certification.valid_until.isnot(None)).all()
        emp_map = {e.id: e for e in db.query(Employee).all()}

        expiring_summary = []
        for c in certs:
            days_left = (c.valid_until - today).days
            if days_left in notify_days_list or (-7 <= days_left <= 0):
                emp = emp_map.get(c.employee_id)
                expiring_summary.append({
                    "employee_name": emp.full_name if emp else "Неизвестный",
                    "category": c.category,
                    "course_name": c.course_name,
                    "valid_until": c.valid_until.strftime("%d.%m.%Y"),
                    "days_left": days_left
                })

        if expiring_summary:
            send_alert_email(
                settings=settings,
                recipient_email=settings.safety_officer_email,
                subject=f"⚠️ [Охрана труда] Истекают сроки аттестаций ({len(expiring_summary)} записей)",
                items=expiring_summary
            )
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_deadlines_job, "cron", hour=8, minute=0)
    scheduler.start()
