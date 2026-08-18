import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from typing import List, Dict

def send_alert_email(settings, recipient_email: str, subject: str, items: List[Dict]):
    if not settings.smtp_user or not recipient_email:
        print("[Mailer] SMTP настройки или получатель не указаны. Пропуск отправки.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Охрана труда и ПБ <{settings.sender_email}>"
    msg["To"] = recipient_email

    rows_html = ""
    for item in items:
        days = item["days_left"]
        if days < 0:
            status_badge = f'<span style="background:#ef4444;color:#fff;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:bold;">Просрочено ({abs(days)} дн.)</span>'
        elif days <= 7:
            status_badge = f'<span style="background:#f97316;color:#fff;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:bold;">Срочно: {days} дн.</span>'
        else:
            status_badge = f'<span style="background:#eab308;color:#000;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:bold;">Истекает: {days} дн.</span>'

        rows_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px; font-weight: bold; color: #1e293b;">{item['employee_name']}</td>
            <td style="padding: 10px; color: #64748b;">{item['category']}</td>
            <td style="padding: 10px; font-weight: 600; color: #0f172a;">{item['course_name']}</td>
            <td style="padding: 10px; color: #334155;">{item['valid_until']}</td>
            <td style="padding: 10px; text-align: center;">{status_badge}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px;">
        <div style="max-width: 760px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0;">
            <div style="background-color: #1e293b; padding: 18px 24px; border-bottom: 4px solid #f59e0b;">
                <h2 style="color: #ffffff; margin: 0; font-size: 18px;">Служба охраны труда и промышленной безопасности</h2>
                <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Уведомление об истечении сроков проверки знаний и допусков</p>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 14px; color: #334155; margin-top: 0;">
                    Внимание! У следующих сотрудников приближается срок плановой проверки знаний или медкомиссии:
                </p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #fef3c7; color: #92400e; text-align: left;">
                            <th style="padding: 10px;">Сотрудник</th>
                            <th style="padding: 10px;">Раздел</th>
                            <th style="padding: 10px;">Программа</th>
                            <th style="padding: 10px;">Действительно до</th>
                            <th style="padding: 10px; text-align: center;">Статус</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
            <div style="background-color: #f8fafc; padding: 12px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0;">
                Автоматическая рассылка сервера обучения персонала
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_port == 587:
                server.starttls()
            if settings.smtp_user and settings.smtp_pass:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        print(f"[Mailer] Уведомление успешно отправлено на {recipient_email}")
        return True
    except Exception as e:
        print(f"[Mailer] Ошибка отправки: {e}")
        return False
