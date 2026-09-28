# O loader lê o lote versionado em data/ e, se for preciso coletar de novo,
# usa requests + BeautifulSoup (coletar_ofertas_por_curso.py). Não precisa
# de navegador: ver docs/adr/0004-coleta-publica-versionada.md.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "run.sh"]
