# Carga de trabalho medida

Este arquivo é gerado por `loader/caracterizar.py` a partir do banco
carregado, e ainda não foi gerado com o recorte real. Depois de
`docker compose up --build`, rode:

```bash
docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
```
