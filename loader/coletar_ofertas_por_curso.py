"""Coleta a oferta histórica pública por curso, sem inferir ocupação.

Uso (dentro do container do loader, que já tem as dependências):
    python coletar_ofertas_por_curso.py --saida ../data/nova_coleta/ofertas
    python coletar_ofertas_por_curso.py --saida ../data/nova_coleta/ofertas --consolidar ../data/nova_coleta

Uma linha = reserva de uma turma para um curso em um semestre ("Vgs
Reservadas"). Vagas reservadas não são vagas ofertadas totais nem vagas
ocupadas. Não utiliza login nem dados de alunos.

Grava um CSV por curso e semestre em --saida (preserva os já existentes) e,
com --consolidar, junta todos em <dir>/ofertas_por_curso.csv, no mesmo
formato que o load_to_db.py lê. Ver docs/adr/0004-... para montar um lote novo.
"""
import argparse
import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HOME = 'https://sigaa.unb.br/sigaa/public/home.jsf'
LISTA = 'https://sigaa.unb.br/sigaa/public/curso/lista.jsf?nivel=G&aba=p-graduacao'
CURSOS = {
    'FGA_SOFT': 'ENGENHARIA DE SOFTWARE',
    'FGA_AERO': 'ENGENHARIA AEROESPACIAL',
    'FGA_AUTO': 'ENGENHARIA AUTOMOTIVA',
    'FGA_ENERG': 'ENGENHARIA DE ENERGIA',
    'FGA_ELET': 'ENGENHARIA ELETRÔNICA',
}


def html(response):
    response.raise_for_status()
    return BeautifulSoup(response.content, 'html.parser')


def entradas(form):
    data = {}
    for e in form.select('input[name], select[name]'):
        if e.get('type') in ('submit', 'button', 'image', 'reset'):
            continue
        if e.name == 'select':
            option = e.select_one('option[selected]') or e.select_one('option')
            data[e['name']] = option.get('value', '') if option else ''
        else:
            data[e['name']] = e.get('value', '')
    return data


def extrair(soup, curso, semestre, url, coletado):
    rows = []
    for table in soup.select('table[id="table_lt"]'):
        group = table.find_previous_sibling('div')
        link = group.find('a') if group else None
        if not link:
            raise ValueError('Cabeçalho da disciplina ausente')
        label = link.get_text(' ', strip=True)
        m = re.fullmatch(r'([A-Z]{2,4}\d{4})\s*-\s*(.+)', label)
        if not m:
            raise ValueError(f'Disciplina não reconhecida: {label}')
        for tr in table.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'], recursive=False)]
            if not cells or not re.fullmatch(r'\d{4}\.[1-4]', cells[0]):
                continue
            if len(cells) != 5 or cells[0] != semestre or not cells[3].isdigit():
                raise ValueError(f'Linha inválida para {semestre}: {cells}')
            ano, periodo = cells[0].split('.')
            rows.append(dict(curso_codigo=curso, disciplina_codigo=m[1], disciplina_nome=m[2],
                             turma_codigo=cells[1], ano=ano, periodo=periodo, docentes=cells[2],
                             vagas_reservadas=int(cells[3]), horario=cells[4],
                             fonte='sigaa_curso_turmas', coletado_em=coletado))
    total = re.search(r'(\d+)\s+Turmas Disponíveis', soup.get_text(' ', strip=True))
    if total and int(total[1]) != len(rows):
        raise ValueError(f'Total anunciado {total[1]} difere das {len(rows)} linhas extraídas')
    if not rows:
        raise ValueError('Consulta sem registros: interrompida para não declarar histórico vazio como válido')
    keys = [(r['disciplina_codigo'], r['turma_codigo']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('Turmas duplicadas dentro do curso e semestre')
    return rows


CAMPOS = ['curso_codigo', 'disciplina_codigo', 'disciplina_nome', 'turma_codigo', 'ano', 'periodo',
          'docentes', 'vagas_reservadas', 'horario', 'fonte', 'coletado_em']


def consolidar(origem: Path, destino: Path) -> Path:
    """Junta os CSVs por curso e semestre num único ofertas_por_curso.csv,
    na ordem curso, semestre, disciplina, turma."""
    linhas = []
    for arquivo in sorted(origem.glob('*.csv')):
        with arquivo.open(encoding='utf-8', newline='') as f:
            linhas.extend(csv.DictReader(f))
    if not linhas:
        raise ValueError(f'Nenhum CSV em {origem}')
    linhas.sort(key=lambda r: (r['curso_codigo'], int(r['ano']), int(r['periodo']),
                               r['disciplina_codigo'], r['turma_codigo']))
    destino.mkdir(parents=True, exist_ok=True)
    saida = destino / 'ofertas_por_curso.csv'
    with saida.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(linhas)
    print(f'{len(linhas)} reservas consolidadas em {saida}', flush=True)
    return saida


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--saida', type=Path, default=Path('data/ofertas_por_curso'))
    ap.add_argument('--curso', choices=CURSOS)
    ap.add_argument('--semestre', help='Ex.: 2022.1; padrão: 2022.1 até 2026.1')
    ap.add_argument('--consolidar', type=Path, metavar='DIR',
                    help='Só junta os CSVs de --saida em DIR/ofertas_por_curso.csv (sem acessar o SIGAA)')
    args = ap.parse_args()
    if args.consolidar:
        consolidar(args.saida, args.consolidar)
        return
    semestres = [args.semestre] if args.semestre else [f'{a}.{p}' for a in range(2022, 2027) for p in (1, 2) if (a, p) <= (2026, 1)]
    if any(not re.fullmatch(r'\d{4}\.[12]', sem) for sem in semestres):
        ap.error('Use um semestre regular no formato AAAA.1 ou AAAA.2')
    args.saida.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        # A sessão JSF deve nascer na home antes de abrir e submeter formulários.
        html(session.get(HOME, timeout=45))
        listing = html(session.get(LISTA, headers={'Referer': HOME}, timeout=45))
        for codigo, nome in CURSOS.items():
            if args.curso and args.curso != codigo:
                continue
            candidates = []
            for tr in listing.find_all('tr'):
                cells = tr.find_all('td', recursive=False)
                if cells and cells[0].get_text(' ', strip=True) == nome:
                    a = tr.select_one('a[href*="portal.jsf"]')
                    if a:
                        candidates.append(urljoin(LISTA, a['href']))
            if len(candidates) != 1:
                raise ValueError(f'{nome}: esperado um portal, encontrados {len(candidates)}')
            portal_url = candidates[0]
            portal = html(session.get(portal_url, timeout=45))
            if 'FCTE' not in portal.get_text(' ', strip=True):
                raise ValueError(f'Unidade do portal não confirmada: {nome}')
            link = portal.select_one('a[href^="turmas.jsf"]')
            if not link:
                raise ValueError(f'Link público de turmas ausente: {nome}')
            url = urljoin(portal_url, link['href'])
            soup = html(session.get(url, headers={'Referer': portal_url}, timeout=45))
            for semestre in semestres:
                path = args.saida / f'{codigo}_{semestre.replace(".", "_")}.csv'
                if path.exists():
                    print(f'Preservado: {path}', flush=True)
                    continue
                form = soup.find('form', id='form')
                if not form or not form.select_one('[name="form:inputAno"]'):
                    raise ValueError('Formulário não encontrado; possível expiração de sessão')
                data = entradas(form)
                ano, periodo = semestre.split('.')
                data.update({'form:inputAno': ano, 'form:inputPeriodo': periodo, 'form:buscar': 'Buscar'})
                response = session.post(urljoin(url, form['action']), data=data,
                                        headers={'Referer': url}, timeout=45)
                soup = html(response)
                coletado = datetime.now(timezone.utc).isoformat()
                rows = extrair(soup, codigo, semestre, url, coletado)
                tmp = path.with_suffix('.tmp')
                with tmp.open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=CAMPOS)
                    writer.writeheader()
                    writer.writerows(rows)
                tmp.replace(path)
                print(f'{nome} {semestre}: {len(rows)} registros -> {path}', flush=True)
                time.sleep(1)
    print('Coleta concluída. Vagas reservadas não informam lotação.', flush=True)


if __name__ == '__main__':
    main()
