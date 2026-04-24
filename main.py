import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from scraper import scrape
from exporter import save_csv
from config import APP_URL


def _build_filename(now: datetime) -> str:
    ms = now.microsecond // 1000
    return f"relatorio-{now.strftime('%Y%m%d-%H%M%S')}{ms:03d}.csv"


def setup_logging(log_file: str) -> None:
    # Força UTF-8 no terminal Windows (cp1252 não suporta alguns caracteres Unicode)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Levantamento de questionários IC5")
    parser.add_argument("url", nargs="?", default=None, help="URL da página com a tabela de produtos")
    parser.add_argument("--log", default=None, help="Caminho do arquivo de log (padrão: mesmo nome do CSV com .log)")
    args = parser.parse_args()

    url = args.url or APP_URL
    if not url:
        print("Erro: informe a URL como argumento ou defina APP_URL no .env")
        print("Uso: python main.py https://sua-aplicacao.com/products")
        sys.exit(1)

    now = datetime.now()
    csv_file = _build_filename(now)
    log_file = args.log or csv_file.replace(".csv", ".log")

    setup_logging(log_file)
    log = logging.getLogger(__name__)
    log.info("=== Levantamento IC5 ===")
    log.info("URL    : %s", url)
    log.info("CSV    : %s", Path(csv_file).resolve())
    log.info("Log    : %s", Path(log_file).resolve())

    records = scrape(url)

    if records:
        save_csv(records, csv_file)
        log.info("CSV salvo em '%s' (%d registro(s)).", csv_file, len(records))
    else:
        log.warning("Nenhum registro extraído.")


if __name__ == "__main__":
    main()
