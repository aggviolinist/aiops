import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import IsolationForest
from mailjet_rest import Client
from dotenv import load_dotenv
import os

# ─────────────────────────────────────────────
#  CONFIG — fill these in before running
# ─────────────────────────────────────────────

load_dotenv()

LOG_FILE_PATH      = "system_logs.txt"        # Path to your log file

os.getenv("API_KEY")

MAILJET_API_KEY    = os.getenv("MAILJET_API_KEY")   # Mailjet API Key
MAILJET_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY")    # Mailjet Secret Key
SENDER_EMAIL       = os.getenv("SENDER_EMAIL")  # Must be verified in Mailjet
SENDER_NAME        = "Log Alerter"            # Display name shown in inbox
RECIPIENT_EMAIL    = os.getenv("RECIPIENT_EMAIL")     # Where to send the alerts
RECIPIENT_NAME     = "KEV"              # Recipient display name

# Only email if at least this many critical items are found (set to 1 to always alert)
MIN_ALERTS_TO_SEND = 1

# Isolation Forest sensitivity (lower = catches more anomalies, higher = stricter)
CONTAMINATION = 0.1
# ─────────────────────────────────────────────


def parse_logs(path: str) -> pd.DataFrame:
    """Read and parse the log file into a structured DataFrame."""
    with open(path, "r") as f:
        logs = f.readlines()

    data = []
    for log in logs:
        parts = log.strip().split(" ", 3)
        if len(parts) < 4:
            continue  # skip malformed lines
        timestamp = parts[0] + " " + parts[1]
        level     = parts[2]
        message   = parts[3]
        data.append([timestamp, level, message])

    df = pd.DataFrame(data, columns=["timestamp", "level", "message"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    return df


def detect_anomalies(df: pd.DataFrame, contamination: float) -> pd.DataFrame:
    """Add anomaly scores using Isolation Forest."""
    level_mapping = {"INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    df["level_score"]     = df["level"].map(level_mapping).fillna(0)
    df["message_length"]  = df["message"].apply(len)

    model = IsolationForest(contamination=contamination, random_state=42)
    df["anomaly_flag"] = model.fit_predict(df[["level_score", "message_length"]])
    df["is_anomaly"]   = df["anomaly_flag"].apply(lambda x: x == -1)
    return df


def get_critical_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return rows that are CRITICAL severity OR flagged as an anomaly.
    Rows are sorted newest-first.
    """
    mask = (df["level"] == "CRITICAL") | df["is_anomaly"]
    critical = df[mask].copy()
    critical = critical.sort_values("timestamp", ascending=False)
    return critical


def build_email_body(critical: pd.DataFrame, total_logs: int) -> str:
    """Build a plain-text email body summarising the critical findings."""
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append(f"Critical Log Alert — {now}")
    lines.append("=" * 60)
    lines.append(f"Total logs analysed : {total_logs}")
    lines.append(f"Critical / anomalous: {len(critical)}")
    lines.append("")

    # Summary counts by level
    level_counts = critical["level"].value_counts().to_dict()
    lines.append("Breakdown by severity:")
    for lvl, cnt in sorted(level_counts.items()):
        lines.append(f"  {lvl:10s} : {cnt}")
    lines.append("")

    # Detailed list
    lines.append("─" * 60)
    lines.append("DETAILED LOG ENTRIES")
    lines.append("─" * 60)
    for _, row in critical.iterrows():
        anomaly_tag = "  [ANOMALY]" if row["is_anomaly"] else ""
        lines.append(f"[{row['timestamp']}] {row['level']}{anomaly_tag}")
        lines.append(f"  {row['message']}")
        lines.append("")

    lines.append("─" * 60)
    lines.append("This alert was generated automatically by critical_log_alerter.py")
    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    """Send a plain-text email via the Mailjet API."""
    mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY), version="v3.1")

    data = {
        "Messages": [
            {
                "From": {
                    "Email": SENDER_EMAIL,
                    "Name":  SENDER_NAME,
                },
                "To": [
                    {
                        "Email": RECIPIENT_EMAIL,
                        "Name":  RECIPIENT_NAME,
                    }
                ],
                "Subject":  subject,
                "TextPart": body,
            }
        ]
    }

    result = mailjet.send.create(data=data)

    # 200 = Mailjet accepted the message for delivery
    if result.status_code != 200:
        raise RuntimeError(
            f"Mailjet returned unexpected status {result.status_code}: "
            f"{result.json()}"
        )


def main():
    print(f"[{datetime.now():%H:%M:%S}] Reading logs from: {LOG_FILE_PATH}")
    df = parse_logs(LOG_FILE_PATH)

    if df.empty:
        print("No valid log entries found. Exiting.")
        return

    print(f"  Parsed {len(df)} log entries. Running anomaly detection…")
    df = detect_anomalies(df, CONTAMINATION)

    critical = get_critical_rows(df)
    print(f"  Found {len(critical)} critical / anomalous entries.")

    if len(critical) < MIN_ALERTS_TO_SEND:
        print("  Below threshold — no email sent.")
        return

    subject = (
        f"🚨 Log Alert: {len(critical)} critical entries detected "
        f"— {datetime.now():%Y-%m-%d %H:%M}"
    )
    body = build_email_body(critical, total_logs=len(df))

    print(f"  Sending alert to {RECIPIENT_EMAIL}…")
    try:
        send_email(subject, body)
        print("  ✅ Email sent successfully.")
    except Exception as e:
        print(f"  ❌ Failed to send email: {e}")
        raise


if __name__ == "__main__":
    main()