from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date, datetime
from database import SessionLocal, Employee, Certification, SystemSettings
from mailer import send_alert_email, send_weekly_excel_report
from excel_generator import generate_safety_excel_report

scheduler = BackgroundScheduler()

def get_full_report_data(db):
    employees = db.query(Employee).all()
    today = date.today()
    employees_data = []
    urgent_items = []
    total_valid = 0
    total_warning = 0
    total_expired = 0

    for emp in employees:
        certs = db.query(Certification).filter(Certification.employee_id == emp.id).all()
        cert_list = []
        for c in certs:
            days_left = None
            status = "valid"
            if c.valid_until:
                days_left = (c.valid_until - today).days
                if days_left < 0:
                    status = "expired"
                    total_expired += 1
                    urgent_items.append({
                        "employee_name": emp.full_name,
                        "category": c.category,
                        "course_name": c.course_name,
                        "valid_until": c.valid_until.strftime("%d.%m.%Y"),
                        "days_left": days_left,
                        "status": status
                    })
                elif days_left <= 30:
                    status = "warning"
                    total_warning += 1
                    urgent_items.append({
                        "employee_name": emp.full_name,
                        "category": c.category,
                        "course_name": c.course_name,
                        "valid_until": c.valid_until.strftime("%d.%m.%Y"),
                        "days_left": days_left,
                        "status": status
                    })
                else:
                    total_valid += 1
            else:
                status = "permanent"
                total_valid += 1

            cert_list.append({
                "id": c.id,
                "category": c.category,
                "course_name": c.course_name,
                "pass_date": c.pass_date.strftime("%d.%m.%Y") if c.pass_date else "-",
                "valid_until": c.valid_until.strftime("%d.%m.%Y") if c.valid_until else "-",
                "days_left": days_left,
                "status": status,
                "file_name": c.file_name or "",
                "file_display_name": c.file_display_name or ""
            })

        employees_data.append({
            "id": emp.id,
            "full_name": emp.full_name,
            "position": emp.position,
            "department": emp.department,
            "email": emp.email,
            "certifications": cert_list
        })

    stats = {
        "total_employees": len(employees),
        "valid_certs": total_valid,
        "warning_certs": total_warning,
        "expired_certs": total_expired
    }
    return employees_data, stats, urgent_items

# Фоновая задача по понедельникам в 08:00
def weekly_excel_report_job():
    print(f"[{datetime.now()}] Запуск еженедельной отправки Excel-отчета...")
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if not settings or not settings.smtp_user or not settings.smtp_pass:
            print("[Weekly Report] SMTP настройки не заполнены, пропуск.")
            return

        recipient = settings.safety_officer_email or settings.smtp_user
        if not recipient:
            return

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
        print(f"[Weekly Report] Результат: {msg}")
    except Exception as e:
        print(f"[Weekly Report Error] {e}")
    finally:
        db.close()

# Ежедневная проверка по интервалам
def daily_interval_check_job():
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if not settings or not settings.smtp_user or not settings.smtp_pass:
            return

        intervals = [int(x.strip()) for x in (settings.notify_days or "30,14,3").split(",") if x.strip().isdigit()]
        today = date.today()
        employees = db.query(Employee).all()

        alert_items = []
        for emp in employees:
            certs = db.query(Certification).filter(Certification.employee_id == emp.id).all()
            for c in certs:
                if c.valid_until:
                    days_left = (c.valid_until - today).days
                    if days_left in intervals:
                        alert_items.append({
                            "employee_name": emp.full_name,
                            "category": c.category,
                            "course_name": c.course_name,
                            "valid_until": c.valid_until.strftime("%d.%m.%Y"),
                            "days_left": days_left
                        })

        if alert_items:
            recipient = settings.safety_officer_email or settings.smtp_user
            send_alert_email(
                settings=settings,
                recipient_email=recipient,
                subject=f"⚠️ ТМК: Напоминание об истечении сроков обучения ({len(alert_items)} записей)",
                items=alert_items
            )
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        # Каждый понедельник в 08:00
        scheduler.add_job(weekly_excel_report_job, CronTrigger(day_of_week='mon', hour=8, minute=0), id="weekly_report")
        # Каждое утро в 07:30 проверка интервалов
        scheduler.add_job(daily_interval_check_job, CronTrigger(hour=7, minute=30), id="daily_check")
        scheduler.start()
        print("[*] Планировщик запущен: еженедельный Excel (Пн 08:00) + ежедневные напоминания (07:30).")
