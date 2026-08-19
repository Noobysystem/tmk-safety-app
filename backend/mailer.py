import smtplib
import ssl
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
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
        return True, "Письмо успешно отправлено!"
    except smtplib.SMTPAuthenticationError:
        return False, "Ошибка авторизации (535): Яндекс отклонил логин/пароль приложения."
    except Exception as e:
        traceback.print_exc()
        return False, f"Ошибка отправки ({type(e).__name__}): {str(e)}"

def send_weekly_excel_report(settings, recipient_email: str, excel_bytes: bytes, filename: str, stats: Dict, urgent_items: List[Dict]) -> Tuple[bool, str]:
    smtp_host = str(settings.smtp_host or "smtp.yandex.ru").strip()
    smtp_port = int(settings.smtp_port or 465)
    smtp_user = str(settings.smtp_user or "").strip()
    smtp_pass = str(settings.smtp_pass or "").strip().replace(" ", "")
    sender = str(settings.sender_email or smtp_user).strip()
    recipient = str(recipient_email or smtp_user).strip()

    if not smtp_user or not smtp_pass or not recipient:
        return False, "Не настроены параметры почты или получатель!"

    today_str = datetime.date.today().strftime("%d.%m.%Y")
    subject = f"📊 Еженедельный отчет по обучению персонала ТМК на {today_str}"

    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header("ТМК Охрана труда", "utf-8")), sender))
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")

    urgent_rows = ""
    for it in urgent_items[:15]: # топ 15 срочных
        color = "#ef4444" if it["status"] == "expired" else "#f59e0b"
        st_text = "ПРОСРОЧЕНО" if it["status"] == "expired" else f"Осталось {it['days_left']} дн."
        urgent_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px 10px; font-weight: bold; color: #1e293b;">{it['employee_name']}</td>
            <td style="padding: 8px 10px; color: #64748b;">{it['category']}</td>
            <td style="padding: 8px 10px; font-weight: 600; color: #0f172a;">{it['course_name']}</td>
            <td style="padding: 8px 10px; text-align: center; font-weight: bold;">{it['valid_until']}</td>
            <td style="padding: 8px 10px; text-align: center;"><span style="background:{color}; color:#fff; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:bold;">{st_text}</span></td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px;">
        <div style="max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #cbd5e1;">
            <div style="background-color: #0f172a; padding: 18px 24px; border-bottom: 4px solid #f59e0b;">
                <h2 style="color: #ffffff; margin: 0; font-size: 18px;">ТМК — Еженедельная выписка по обучению и аттестациям</h2>
                <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Отчет на {today_str}. Подробная таблица прикреплена к письму в формате Excel.</p>
            </div>
            
            <div style="padding: 20px;">
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 13px;">
                        <tr>
                            <td style="background:#f8fafc; border:1px solid #e2e8f0; padding:12px; border-radius:6px;">
                                <div style="color:#64748b; font-size:11px; text-transform:uppercase; font-weight:bold;">Сотрудников</div>
                                <div style="font-size:22px; font-weight:900; color:#1e293b; margin-top:4px;">{stats['total_employees']}</div>
                            </td>
                            <td style="background:#f0fdf4; border:1px solid #bbf7d0; padding:12px; border-radius:6px;">
                                <div style="color:#166534; font-size:11px; text-transform:uppercase; font-weight:bold;">Действующих</div>
                                <div style="font-size:22px; font-weight:900; color:#16a34a; margin-top:4px;">{stats['valid_certs']}</div>
                            </td>
                            <td style="background:#fffbeb; border:1px solid #fde68a; padding:12px; border-radius:6px;">
                                <div style="color:#92400e; font-size:11px; text-transform:uppercase; font-weight:bold;">Истекают скоро</div>
                                <div style="font-size:22px; font-weight:900; color:#d97706; margin-top:4px;">{stats['warning_certs']}</div>
                            </td>
                            <td style="background:#fef2f2; border:1px solid #fecaca; padding:12px; border-radius:6px;">
                                <div style="color:#991b1b; font-size:11px; text-transform:uppercase; font-weight:bold;">Просрочено</div>
                                <div style="font-size:22px; font-weight:900; color:#dc2626; margin-top:4px;">{stats['expired_certs']}</div>
                            </td>
                        </tr>
                    </table>
                </div>

                {f'''
                <h3 style="font-size: 14px; color: #1e293b; margin: 20px 0 10px 0;">⚠️ Требуют внимания в ближайшее время:</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead>
                        <tr style="background-color: #fbbf24; color: #1e293b; text-align: left;">
                            <th style="padding: 8px 10px;">Сотрудник</th>
                            <th style="padding: 8px 10px;">Раздел</th>
                            <th style="padding: 8px 10px;">Программа</th>
                            <th style="padding: 8px 10px; text-align: center;">Срок</th>
                            <th style="padding: 8px 10px; text-align: center;">Статус</th>
                        </tr>
                    </thead>
                    <tbody>{urgent_rows}</tbody>
                </table>
                ''' if urgent_items else '<p style="color:#16a34a; font-weight:bold; font-size:13px;">✅ Все допуски и аттестации в норме, срочных действий не требуется!</p>'}

                <div style="margin-top: 25px; padding: 12px; background: #f8fafc; border-left: 4px solid #f59e0b; font-size: 12px; color: #475569;">
                    📎 Полный реестр со всеми сотрудниками и допусками прикреплен во вложении: <b>{filename}</b>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Прикрепляем Excel
    attachment = MIMEApplication(excel_bytes, Name=filename)
    attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
    msg.attach(attachment)

    try:
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True, f"Еженедельный отчет успешно отправлен на {recipient}!"
    except Exception as e:
        traceback.print_exc()
        return False, f"Ошибка отправки еженедельного отчета ({type(e).__name__}): {str(e)}"
