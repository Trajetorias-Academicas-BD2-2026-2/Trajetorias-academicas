{% docs vagas_reservadas %}
Lugares que a turma guardou para alunos do curso. É o campo **"Vgs Reservadas"** da página pública
*Turmas do curso* do SIGAA, copiado sem transformação. **Não** é vaga ocupada nem oferta total da turma.

Linhagem: SIGAA › Turmas do curso › "Vgs Reservadas" → `data/coleta_publica_2026-09-28/ofertas_por_curso.csv`
(coluna `vagas_reservadas`, conferida por SHA-256) → `public.reserva_vaga.vagas_reservadas` → `stg_reservas` → `fct_reservas`.
{% enddocs %}

{% docs curso_codigo %}
Código do curso no observatório (FGA_SOFT, FGA_AERO, FGA_AUTO, FGA_ELET, FGA_ENERG). Vem da listagem pública de
cursos de graduação do SIGAA (`cursos.csv` do lote) → `public.curso.codigo`.
{% enddocs %}

{% docs curso_nome %}
Nome oficial do curso na listagem pública do SIGAA (`public.curso.nome`).
{% enddocs %}

{% docs disciplina_codigo %}
Código do componente curricular no SIGAA (ex.: FGA0137). O prefixo indica o departamento que oferece a turma
(FGA = FCTE, MAT = Matemática, IFD = Física...). Origem: páginas de turmas e catálogo de componentes → `public.disciplina.codigo`.
{% enddocs %}

{% docs disciplina_nome %}
Nome do componente no catálogo público do SIGAA (`public.disciplina.nome`). Histórico de mudanças em `dim_disciplina` (SCD 2).
{% enddocs %}

{% docs semestre %}
Semestre letivo da turma, no formato AAAA.N (tempo do evento). Origem: filtro ano/período da página de turmas do SIGAA →
`public.turma.ano` e `public.turma.periodo`. Só entram semestres encerrados segundo o calendário oficial.
{% enddocs %}

{% docs semestre_key %}
Chave numérica do semestre: ano × 10 + período (ex.: 20261). Liga o fato a `dim_semestre`.
{% enddocs %}

{% docs obrigatoria %}
Verdadeiro se a disciplina é obrigatória no **currículo de referência de 2026.1** do curso (conjunto fixo usado na pergunta de gestão).
Origem: estruturas curriculares públicas do SIGAA → `public.curriculo_componente.natureza`, view `curriculo_referencia`.
{% enddocs %}

{% docs unidade_origem %}
Prefixo alfabético do código da disciplina, que identifica o departamento que oferece a turma (FGA, MAT, IFD, CIC...).
{% enddocs %}

{% docs de_outra_unidade %}
Verdadeiro quando a disciplina não é da FCTE (`public.disciplina.unidade_id` nulo).
{% enddocs %}

{% docs turma_id %}
Identificador interno da turma (`public.turma.id`); a turma é única por disciplina, código da turma, ano e período.
{% enddocs %}

{% docs ingerido_em %}
Quando a linha entrou no banco OLTP (tempo de ingestão, `public.reserva_vaga.ingerido_em`).
{% enddocs %}

{% docs processado_em %}
Quando o dbt gravou a linha nesta tabela (tempo de processamento).
{% enddocs %}
