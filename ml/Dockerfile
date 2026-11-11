FROM python:3.12-slim

WORKDIR /workspace
COPY ml/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY ml /workspace/ml

# O modelo (cerca de 470 MB) é baixado na primeira execução para este volume,
# não fica na imagem.
ENV MODELO_DIR=/modelos
CMD ["python", "/workspace/ml/gerar_embeddings.py"]
