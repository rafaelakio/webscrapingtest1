import csv
from pathlib import Path

FIELDS = [
    "produto",
    "risk_completion_date",
    "risk_expiration_date",
    "risk_responder",
    "risk_status",
    "access_completion_date",
    "access_expiration_date",
    "access_responder",
    "access_status",
]


def save_csv(records: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"\nArquivo salvo: {path} ({len(records)} registro(s))")
