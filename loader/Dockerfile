# Imagem oficial do Playwright já traz o Chromium e as dependências do SO,
# necessárias porque o SIGAA é um app JSF (postback com ViewState) e não
# expõe os dados por um GET simples — precisamos de um browser de verdade.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "run.sh"]
