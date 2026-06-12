# MeuDanfe API — Scripts de importação e download de NF-e

Este repositório contém scripts auxiliares para:
- importar chaves de acesso de um arquivo Excel para um banco SQLite,
- enviar (push) as chaves para a API externa,
- e baixar os arquivos XML retornados pela API.

Ordem de execução (RECOMENDADO)
1. `xlsx_to_sqlite.py` — criar a base SQLite a partir do Excel.
2. `push_chaves.py` — enviar (PUT) cada chave para a API e registrar status.
3. `fetch_xml.py` — baixar os XMLs para chaves com status "OK" e salvar no disco / banco.

Requisitos
- Python 3.8+
- Bibliotecas: `pandas`, `python-dotenv`, `requests`
- (opcional) `poetry` se quiser usar os comandos do `Makefile`

Instalação rápida
1. Criar um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.\.venv\\Scripts\\Activate  # Windows PowerShell
```

2. Instalar dependências:

```bash
pip install pandas python-dotenv requests
# ou, se usar poetry:
# poetry install
```

Configurar credenciais
- Defina a variável de ambiente `APP_KEY` com a sua chave da API.
- Você pode criar um arquivo `.env` na raiz com:

```text
APP_KEY=suachave_aqui
```

Arquivos importantes
- `chaves_de_acesso.xlsx` — planilha de entrada (ex.: aba `Planilha1` com coluna "Chave NF-e").
- `xlsx_to_sqlite.py` — converte planilha(s) para `chaves_de_acesso.db`.
- `push_chaves.py` — faz PUT para `https://api.meudanfe.com.br/v2/fd/add/{key}` e atualiza `status_api`/`retorno_api`.
- `fetch_xml.py` — faz GET para `https://api.meudanfe.com.br/v2/fd/get/xml/{key}`, grava XML em `arquivos_xml/` e atualiza a DB.
- `Makefile` — alvos que encapsulam os comandos (ver exemplos abaixo).

Uso (exemplos)

Usando o Makefile (recomendado se tiver poetry):

```bash
# 1) Criar o banco a partir do Excel (exporta a aba Planilha1)
make populate-db

# 2) Enviar chaves para a API (faz update no DB)
make push-chaves

# 3) Buscar os XMLs para chaves com status OK
make fetch-xml
```

Chamadas diretas (sem Makefile)

```bash
# 1) Converter Excel -> SQLite
python xlsx_to_sqlite.py --excel chaves_de_acesso.xlsx --db chaves_de_acesso.db --sheets "Planilha1"

# 2) Enviar chaves (escreve status_api e retorno_api) — aguarda 1s entre requests
python push_chaves.py --db chaves_de_acesso.db --column "Chave NF-e" --update --wait 1.0

# 3) Baixar XMLs (escreve xml e retorno_xml no DB e salva arquivos em arquivos_xml/)
python fetch_xml.py --db chaves_de_acesso.db --table "Planilha1" --column "Chave NF-e" --update --wait 1.0
```

Observações e dicas
- `xlsx_to_sqlite.py` NÃO sobrescreve um arquivo de banco existente — remova o DB antigo ou escolha outro nome se quiser recriar.
- Os scripts assumem que a coluna com a chave chama-se `"Chave NF-e"` por padrão; use `--column` para outra coluna.
- `push_chaves.py` exige `APP_KEY`; se a API retornar `"Payment Required"` o script aborta com erro (comportamento intencional).
- `fetch_xml.py` tenta extrair o campo `name` do JSON de resposta para nomear o arquivo XML; se não houver nome a gravação do arquivo pode falhar (o script registra erros no campo `retorno_xml`).
- Os XMLs bem-sucedidos são salvos em `arquivos_xml/` e a coluna `xml` na DB é atualizada.
- Ajuste `--wait` para reduzir pressão na API (padrão 1.0s) **Não coloque menos que 1s para não tomar ban no IP**.
- Faça um backup do Excel e do DB antes de rodar em produção.

Problemas / Debug
- Rode os scripts com `-v` para logging em DEBUG.
- Verifique os campos `status_api`, `retorno_api` e `retorno_xml` na tabela do SQLite para entender erros/respostas da API.