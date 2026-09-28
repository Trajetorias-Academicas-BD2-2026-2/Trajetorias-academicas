# Validação realizada

- 45 consultas públicas por curso e semestre extraídas no navegador: todas com registros.
- 1.786 chaves únicas `(curso, disciplina, turma, ano, período)`, sem duplicatas.
- 735 chaves de turma sem curso; compartilhamento entre cursos preservado.
- 585 códigos únicos no catálogo de componentes da FCTE.
- Seis estruturas curriculares, 625 vínculos extraídos das 12 abas de cada estrutura.
- Cada linha histórica confere com o semestre solicitado.
- Coletor HTTP executado de verdade para Software/2022.1: 60 registros.
- Comparação navegador × HTTP: mesmas disciplinas, turmas, vagas reservadas, horários e docentes, com normalização somente dos espaços em branco.
- Coletor HTTP não foi executado novamente para as outras 44 consultas; os CSVs entregues vêm da coleta pelo navegador.
- Ocupação histórica não obtida. Pré-requisitos: coleta parcial de 23 componentes.
- Banco OLTP original, Docker Compose e benchmarks não executados nesta coleta.
