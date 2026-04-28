import csv
from pathlib import Path

FIELDS = [
    "nome_aplicacao",
    "sigla_app",
    "repo",
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


def save_csv(records: list[dict], path: str, append: bool = False) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    file_exists = Path(path).exists()
    mode = "a" if append else "w"
    with open(path, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", delimiter=";")
        if not (append and file_exists):
            writer.writeheader()
        writer.writerows(records)
