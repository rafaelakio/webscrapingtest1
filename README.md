# Web Scraping Test 1

Automatiza a extração de dados de questionários de produtos IC5 via scraping baseado em navegador. Coleta metadados de aplicações, avaliações de risco e revisões de acesso em relatórios CSV compatíveis com Excel.

## Pré-requisitos

- Python 3.8+
- Google Chrome ou Microsoft Edge
- ChromeDriver ou EdgeDriver compatível

## Instalação

```bash
git clone https://github.com/rafaelakio/webscrapingtest1.git
cd webscrapingtest1
pip install -r requirements.txt
cp .env.example .env
# Edite o .env com suas configurações
```

## Como Usar

```bash
python main.py
```

O script irá:
1. Abrir o navegador e aguardar login manual (SSO)
2. Navegar pelos questionários IC5
3. Extrair dados dos painéis de cada aplicação
4. Exportar resultados em CSV (UTF-8-SIG para compatibilidade com Excel)

## Arquitetura

- **`main.py`**: Ponto de entrada CLI e orquestrador do pipeline
- **`scraper.py`**: Lógica de automação Selenium e extração de dados
- **`exporter.py`**: Serialização CSV e gerenciamento de arquivos
- **`config.py`**: Constantes globais e configuração de ambiente

Para mais detalhes, consulte [CLAUDE.md](CLAUDE.md).

## Como Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para diretrizes de contribuição.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.
