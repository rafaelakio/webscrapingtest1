import asyncio
from scraper import scrape
from exporter import save_csv
from config import OUTPUT_FILE, APP_URL


def main():
    if not APP_URL:
        print("Erro: defina APP_URL no arquivo .env antes de executar.")
        return

    print("=== Levantamento IC5 ===\n")
    records = asyncio.run(scrape())

    if records:
        save_csv(records, OUTPUT_FILE)
    else:
        print("Nenhum registro extraído.")


if __name__ == "__main__":
    main()
