# Python SMTP Bulk Mailer

A reliable, lightweight Python script designed for sending personalized HTML emails via SMTP (configured for Mailgun by default). It renders dynamic email templates using Jinja2, reads recipient lists from CSV files, handles both common and per-recipient attachments, and logs delivery results.

## Key Features

- **Jinja2 Templating:** Full support for dynamic placeholders and conditions in both HTML templates and email subjects.
- **Robust Cyrillic & UTF-8 Handling:** Automatically encodes headers to prevent missing spaces and encoding artifacts in non-ASCII subjects.
- **Attachment Support:** Easily send global attachments to all recipients, custom attachments specified per row in CSV, or both.
- **Privacy & Security:**
  - Credentials and sensitive configurations are stored in an `.env` file (12-Factor App approach).
  - Proper BCC handling without exposing addresses in headers.
- **Spam Filter Friendly:** Sends messages as `multipart/alternative` with plain-text fallback.
- **Fault-Tolerant:** Automatic reconnect mechanism in case of connection dropouts during mass mailing.
- **Delivery Reporting:** Automatically exports a `delivery_report.csv` detailing the status of each sent message.

---

## Project Structure

```text
.
├── .env                  # Configuration & SMTP credentials (git-ignored)
├── .env.example          # Sample environment variables
├── send_emails.py        # Main execution script
├── recipients.csv        # Recipient list and variables
├── template.html         # Responsive HTML email template
├── attachments/          # Folder for files to attach
└── delivery_report.csv   # Auto-generated execution report
```

---

## Getting Started

### 1. Prerequisites

Python 3.10 or newer is recommended.

### 2. Install Dependencies

```bash
pip install -r req.txt
```

### 3. Environment Configuration

Create a `.env` file in the root directory (refer to `.env.example`):

```ini
SMTP_SERVER=smtp.eu.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your-smtp-password

SENDER_NAME=HearMe Team
SENDER_EMAIL=info@your-domain.mailgun.org
BCC_EMAIL=audit@your-domain.mailgun.org

DEFAULT_SUBJECT={{ name }}, thank you for attending the HearMe presentation!
SEND_DELAY_SECONDS=1.0
COMMON_ATTACHMENTS=
```

### 4. Prepare Recipients

Define your contacts in `recipients.csv` (refer to `recipients.csv.example`):

```csv
email,name,company,subject,attachments
olena@example.com,Olena,TechCorp,,attachments/invoice1.pdf;attachments/invoice2.pdf
ivan@example.com,Ivan,SoftDev,Special offer for Ivan,
```

### 5. Run the Script

```bash
python send_emails.py
```

Check the terminal output and inspect `delivery_report.csv` upon completion to review delivery statuses.

---

## License

MIT License. Free for personal and commercial use.
