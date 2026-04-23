import argparse
from scraper import scrape
from exporter import save_csv
from config import OUTPUT_FILE, APP_URL


def main():
    parser = argparse.ArgumentParser(description="Levantamento de questionários IC5")
    parser.add_argument("url", nargs="?", default=None, help="URL da página com a tabela de produtos")
    args = parser.parse_args()

    url = args.url or APP_URL
    if not url:
        print("Erro: informe a URL como argumento ou defina APP_URL no .env")
        print("Uso: python main.py https://sua-aplicacao.com/products")
        return

    print("=== Levantamento IC5 ===\n")
    records = scrape(url)

    if records:
        save_csv(records, OUTPUT_FILE)
    else:
        print("Nenhum registro extraído.")


if __name__ == "__main__":
    main()
