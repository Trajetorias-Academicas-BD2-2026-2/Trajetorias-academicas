FROM python:3.12-slim
WORKDIR /app
COPY app.py .
ENV PAUTA_DB=/dados/pauta.sqlite3
CMD ["python", "app.py"]
