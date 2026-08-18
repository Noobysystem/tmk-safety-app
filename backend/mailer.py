import smtplib
import ssl
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from typing import List, Dict, Tuple

def send_alert_email(settings, recipient_email: str, subject: str, items: List[Dict]) -> Tuple[bool, str]:
    smtp_host = str(settings.smtp_host or "smtp.yandex.ru").strip()
    smtp_port = int(settings.smtp_port or 465)
    smtp_user = str(settings.smtp_user or "").strip()
    smtp_pass = str(settings.smtp_pass or "").strip().replace(" ", "")
    sender = str(settings.sender_email or smtp_user).strip()
    recipient = str(recipient_email or smtp_user).strip()

    if not smtp_user or not smtp_pass:
        return False, "Заполните логин и пароль приложения Яндекса!"
    if not recipient:
        return False, "Укажите Email получателя!"

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((str(Header("ТМК Охрана труда", "utf-8")), sender))
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")

    rows_html = ""
    for item in items:
        days = item.get("days_left", 0)
        badge = f'<span style="background:#f59e0b;color:#000;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:bold;">Истекает: {days} дн.</span>'
        rows_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px; font-weight: bold; color: #1e293b;">{item['employee_name']}</td>
            <td style="padding: 10px; color: #64748b;">{item['category']}</td>
            <td style="padding: 10px; font-weight: 600; color: #0f172a;">{item['course_name']}</td>
            <td style="padding: 10px; color: #334155;">{item['valid_until']}</td>
            <td style="padding: 10px; text-align: center;">{badge}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px;">
        <div style="max-width: 760px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0;">
            <div style="background-color: #1e293b; padding: 18px 24px; border-bottom: 4px solid #f59e0b;">
                <h2 style="color: #ffffff; margin: 0; font-size: 18px;">Служба охраны труда и промышленной безопасности</h2>
                <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Тестовое уведомление системы обучения персонала</p>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 14px; color: #334155;">Система автоматических напоминаний успешно настроена и готова к работе!</p>
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
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        print(f"[SMTP] Подключение к {smtp_host}:{smtp_port} для {smtp_user}...")
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        print("[SMTP] Письмо успешно отправлено!")
        return True, "Письмо успешно отправлено!"
    except smtplib.SMTPAuthenticationError as e:
        err_msg = "Ошибка авторизации (535): Яндекс отклонил логин/пароль. Убедитесь, что пароль создан для Почты."
        print(f"[SMTP Error] {err_msg} ({e})")
        return False, err_msg
    except Exception as e:
        traceback.print_exc()
        err_msg = f"Ошибка отправки ({type(e).__name__}): {str(e)}"
        print(f"[SMTP Error] {err_msg}")
        return False, err_msg
