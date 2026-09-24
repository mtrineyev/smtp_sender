import csv
import mimetypes
import os
import re
import smtplib
import time
from dataclasses import dataclass
from email.header import Header
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv
from jinja2 import Template

# Завантажуємо налаштування з .env
load_dotenv()


# =====================================================================
# 1. СТРУКТУРА КОНФІГУРАЦІЇ
# =====================================================================
@dataclass
class Config:
    """Зберігає та валідує всі параметри розсилки."""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender_name: str
    sender_email: str
    bcc_email: str
    default_subject: str
    delay_seconds: float
    common_attachments: list[str]
    csv_file: str = "recipients.csv"
    template_file: str = "template.html"
    report_file: str = "delivery_report.csv"

    @classmethod
    def load(cls) -> "Config":
        """Зчитує параметри з .env та перевіряє обов'язкові значення."""
        def get_required(var_name: str) -> str:
            val = os.getenv(var_name, "").strip()
            if not val:
                raise ValueError(f"Помилка в .env! Відсутнє обов'язкове поле: {var_name}")
            return val

        raw_attachments = os.getenv("COMMON_ATTACHMENTS", "").strip()
        common_list = [f.strip() for f in raw_attachments.split(";") if f.strip()]

        return cls(
            smtp_server=os.getenv("SMTP_SERVER", "smtp.eu.mailgun.org").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "587").strip()),
            smtp_username=get_required("SMTP_USERNAME"),
            smtp_password=get_required("SMTP_PASSWORD"),
            sender_name=os.getenv("SENDER_NAME", "Support").strip(),
            sender_email=get_required("SENDER_EMAIL"),
            bcc_email=os.getenv("BCC_EMAIL", "").strip(),
            default_subject=os.getenv("DEFAULT_SUBJECT", "Інформація від HearMe").strip(),
            delay_seconds=float(os.getenv("SEND_DELAY_SECONDS", "1.0").strip()),
            common_attachments=common_list,
        )


# =====================================================================
# 2. ДОПОМІЖНІ ФУНКЦІЇ
# =====================================================================
def is_valid_email(email: str) -> bool:
    """Перевіряє коректність формату електронної пошти."""
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email.strip()))


def format_header_text(text: str) -> str:
    """
    Безпечно кодує кириличний текст для заголовків email (Subject, From),
    гарантуючи відсутність символів переносу рядка (\n, \r) та збереження пробілів.
    """
    # Встановлюємо maxlinelen=998 (максимум за стандартом RFC),
    # а будь-які можливі перенесення рядків замінюємо пробілом.
    encoded = Header(text, "utf-8", maxlinelen=998).encode()
    return encoded.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def attach_file(message: EmailMessage, file_path_str: str) -> bool:
    """
    Додає файл як вкладення до листа.
    Повертає True при успіху, False при помилці.
    """
    path = Path(file_path_str.strip())
    if not path.is_file():
        print(f"    [!] Попередження: Вкладення не знайдено: {path}")
        return False

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        maintype, subtype = "application", "octet-stream"
    else:
        maintype, subtype = mime_type.split("/", 1)

    try:
        with open(path, "rb") as f:
            file_data = f.read()

        message.add_attachment(
            file_data,
            maintype=maintype,
            subtype=subtype,
            filename=path.name
        )
        print(f"    [+] Додано файл: {path.name}")
        return True
    except Exception as e:
        print(f"    [!] Не вдалося прочитати файл {path.name}: {e}")
        return False


def create_smtp_connection(config: Config) -> smtplib.SMTP:
    """Встановлює захищене TLS-з'єднання з Mailgun."""
    server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=30)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(config.smtp_username, config.smtp_password)
    return server


# =====================================================================
# 3. ОСНОВНИЙ ПРОЦЕС РОЗСИЛКИ
# =====================================================================
def run_mailer():
    # 1. Завантаження конфігурації
    try:
        config = Config.load()
    except ValueError as err:
        print(f"[Критична помилка конфігурації] {err}")
        return

    # 2. Перевірка файлів
    if not Path(config.csv_file).is_file():
        print(f"[Помилка] Файл зі списком адрес '{config.csv_file}' не знайдено.")
        return

    if not Path(config.template_file).is_file():
        print(f"[Помилка] Файл шаблону '{config.template_file}' не знайдено.")
        return

    # 3. Зчитування шаблону та списку адресатів
    with open(config.template_file, "r", encoding="utf-8") as f:
        html_template = Template(f.read())

    default_subject_template = Template(config.default_subject)

    with open(config.csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        recipients = list(reader)

    if not recipients:
        print("Файл recipients.csv порожній.")
        return

    print(f"Знайдено записів для розсилки: {len(recipients)}")
    print(f"Підключення до {config.smtp_server}:{config.smtp_port}...")

    report_rows = []
    smtp_server = None

    try:
        smtp_server = create_smtp_connection(config)
        print("Авторизація успішна. Починаємо розсилку...\n" + "=" * 60)

        for index, row in enumerate(recipients, start=1):
            email = row.get("email", "").strip()
            name = row.get("name", "").strip()
            print(f"[{index}/{len(recipients)}] Обробка: {email} ({name})")

            if not email or not is_valid_email(email):
                reason = "Некоректний або порожній email"
                print(f"    [-] Пропущено: {reason}")
                report_rows.append({"email": email, "status": "FAILED", "details": reason})
                continue

            # Рендеринг теми листа
            raw_subject = row.get("subject", "").strip()
            if raw_subject:
                subject_text = Template(raw_subject).render(**row)
            else:
                subject_text = default_subject_template.render(**row)

            # Рендеринг тіла листа
            html_content = html_template.render(**row)
            plain_text_content = (
                f"Доброго дня, {name}!\n"
                f"Будь ласка, перегляньте цей лист у поштовому клієнті з підтримкою HTML."
            )

            # Створюємо лист
            msg = EmailMessage()
            
            # Безпечно формуємо заголовок теми без небезпечних переносів рядків
            msg["Subject"] = format_header_text(subject_text)
            
            # Безпечно формуємо поле From
            encoded_name = format_header_text(config.sender_name)
            msg["From"] = f"{encoded_name} <{config.sender_email}>"
            msg["To"] = email

            delivery_recipients = [email]
            if config.bcc_email and is_valid_email(config.bcc_email):
                delivery_recipients.append(config.bcc_email)

            msg.set_content(plain_text_content)
            msg.add_alternative(html_content, subtype="html")

            # Вкладення
            for common_path in config.common_attachments:
                attach_file(msg, common_path)

            personal_files = row.get("attachments", "").split(";")
            for p_path in personal_files:
                if p_path.strip():
                    attach_file(msg, p_path)

            # Відправка
            sent_successfully = False
            for attempt in range(2):
                try:
                    smtp_server.send_message(msg, to_addrs=delivery_recipients)
                    sent_successfully = True
                    break
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPSenderRefused):
                    print(f"    [!] Втрачено зв'язок. Спроба перепідключення ({attempt + 1}/2)...")
                    try:
                        smtp_server = create_smtp_connection(config)
                    except Exception as reconnect_err:
                        print(f"    [!] Не вдалося перепідключитися: {reconnect_err}")
                except Exception as send_err:
                    print(f"    [!] Помилка відправки: {send_err}")
                    report_rows.append({"email": email, "status": "FAILED", "details": str(send_err)})
                    break

            if sent_successfully:
                print(f"    [V] Успішно надіслано!")
                report_rows.append({"email": email, "status": "SUCCESS", "details": "Sent"})

            time.sleep(config.delay_seconds)

    except Exception as fatal_err:
        print(f"\n[Критична помилка]: {fatal_err}")
    finally:
        if smtp_server:
            try:
                smtp_server.quit()
            except Exception:
                pass

        if report_rows:
            with open(config.report_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["email", "status", "details"])
                writer.writeheader()
                writer.writerows(report_rows)
            print("=" * 60)
            print(f"Звіт про розсилку збережено у: {config.report_file}")


if __name__ == "__main__":
    run_mailer()
