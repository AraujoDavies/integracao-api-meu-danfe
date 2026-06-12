.PHONY: populate-db
populate-db:
	poetry run python code/xlsx_to_sqlite.py --excel chaves_de_acesso.xlsx --db chaves_de_acesso.db --sheets "Planilha1"

.PHONY: push-chaves
push-chaves:
	poetry run python code/push_chaves.py --db chaves_de_acesso.db --column "Chave NF-e" --update --wait 1.0

.PHONY: fetch-xml
fetch-xml:
	poetry run python code/fetch_xml.py --db chaves_de_acesso.db --column "Chave NF-e" --update --wait 1.0

.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  populate-db    : Populate the database with the data from the Excel file"
	@echo "  push-chaves    : Push the chaves to the API"
	@echo "  fetch-xml      : Fetch the XML from the API"
	@echo "  help           : Show this help message"