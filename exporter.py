import csv
from pathlib import Path

FIELDS = [
    "produto",
    "sigla_app",
    "url",
    "risk_overall_risk",
    "risk_responder",
    "risk_status",
    "risk_completion_date",
    "risk_expiration_date",
    "access_responder",
    "access_status",
    "access_completion_date",
]


def save_csv(records: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        writer.writerows(records)
