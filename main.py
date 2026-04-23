import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from scraper import scrape
from exporter import save_csv
from config import OUTPUT_FILE, APP_URL


def setup_logging(log_file: str) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Levantamento de questionários IC5")
    parser.add_argument("url", nargs="?", default=None, help="URL da página com a tabela de produtos")
    parser.add_argument("--log", default=None, help="Caminho do arquivo de log (padrão: levantamento_YYYYMMDD_HHMMSS.log)")
    args = parser.parse_args()

    url = args.url or APP_URL
    if not url:
        print("Erro: informe a URL como argumento ou defina APP_URL no .env")
        print("Uso: python main.py https://sua-aplicacao.com/products")
        sys.exit(1)

    log_file = args.log or f"levantamento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    setup_logging(log_file)

    log = logging.getLogger(__name__)
    log.info("=== Levantamento IC5 ===")
    log.info("URL: %s", url)
    log.info("Log: %s", Path(log_file).resolve())

    records = scrape(url)

    if records:
        save_csv(records, OUTPUT_FILE)
        log.info("CSV salvo em '%s' (%d registro(s)).", OUTPUT_FILE, len(records))
    else:
        log.warning("Nenhum registro extraído.")


if __name__ == "__main__":
    main()
