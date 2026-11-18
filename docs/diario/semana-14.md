# Semana 14 (10/11 a 16/11)

## O que foi medido
- Camada vetorial com pgvector entrou na `main` (PR #1, commit `4b591c1`, 11/11):
  textos de disciplinas e cursos vetorizados e busca de vizinhos funcionando
  ([`evidencias/busca-vetorial.txt`](../evidencias/busca-vetorial.txt)).
- Roteiro e página de apresentação da E3 escritos (commits `8ff2848` a `71ea076`, 16/11).

## O que surpreendeu
- Na busca de vizinhos de uma disciplina de banco de dados, "Sistemas de Banco de Dados 1" e "Sistemas de
  Bancos de Dados" aparecem lado a lado (distâncias 0,026 e 0,027): provavelmente a mesma
  matéria em códigos diferentes (FGA0137 e FGA0135). A busca pode servir para achar equivalências entre
  currículos, não só disciplinas "parecidas".

## O que foi decidido
- A camada vetorial fica opcional (perfil `ml`) e fora do `docker compose up`,
  porque o modelo tem cerca de 470 MB.

## Próxima semana
- [ ] Revisar E1–E3 contra os checklists e começar a E4 (Squad).
