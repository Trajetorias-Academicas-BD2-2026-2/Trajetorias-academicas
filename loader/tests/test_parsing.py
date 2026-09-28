"""Testes do parsing, das regras de semestre e do coletor (sem rede).

    docker compose run --rm loader python -m unittest discover -s tests -v
"""

import csv
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from coletar_ofertas_por_curso import CAMPOS, consolidar, extrair  # noqa: E402
from parsing import extrair_horario, inferir_turno, normalizar_natureza, parse_docentes  # noqa: E402
from semestres import encerrado_em, intervalo, ler_calendario, parse_semestre  # noqa: E402


class TestHorarioETurno(unittest.TestCase):
    def test_horario_ignora_datas(self):
        self.assertEqual(extrair_horario(["35T23 (09/03/2026 - 11/07/2026)"]), "35T23")

    def test_horario_com_mais_de_um_bloco(self):
        self.assertEqual(extrair_horario(["24M12 6T34"]), "24M12 6T34")

    def test_turma_sem_horario(self):
        self.assertEqual(extrair_horario(["A definir"]), "")
        self.assertEqual(inferir_turno(""), "SEM_HORARIO")

    def test_turnos(self):
        self.assertEqual(inferir_turno("246M12"), "DIURNO")
        self.assertEqual(inferir_turno("24M12 6T34"), "DIURNO")
        self.assertEqual(inferir_turno("35N12"), "NOTURNO")
        self.assertEqual(inferir_turno("2T45 4N12"), "INTEGRAL")


class TestCamposTextuais(unittest.TestCase):
    def test_varios_docentes(self):
        self.assertEqual(
            parse_docentes("CRISTIANE SOARES RAMOS , GEORGE MARSICANO CORREA"),
            ["CRISTIANE SOARES RAMOS", "GEORGE MARSICANO CORREA"],
        )

    def test_docente_com_carga_horaria_e_repetido(self):
        self.assertEqual(parse_docentes("FULANO (30h) , FULANO"), ["FULANO"])

    def test_sem_docente(self):
        self.assertEqual(parse_docentes(""), [])

    def test_natureza(self):
        self.assertEqual(normalizar_natureza("Obrigatória"), "OBRIGATORIA")
        self.assertEqual(normalizar_natureza("Optativa"), "OPTATIVA")
        with self.assertRaises(ValueError):
            normalizar_natureza("Complementar")


CALENDARIO = Path(os.getenv("CALENDARIO", Path(__file__).resolve().parents[2] / "data" / "calendario_academico.csv"))


class TestSemestres(unittest.TestCase):
    def test_intervalo(self):
        s = intervalo("2022.1", "2026.1")
        self.assertEqual((len(s), s[0], s[-1]), (9, (2022, 1), (2026, 1)))

    def test_periodo_invalido(self):
        with self.assertRaises(ValueError):
            parse_semestre("2024.3")


@unittest.skipUnless(CALENDARIO.exists(), "calendário acadêmico não montado")
class TestCalendario(unittest.TestCase):
    def setUp(self):
        self.cal = ler_calendario(str(CALENDARIO))

    def test_todo_semestre_do_recorte_tem_encerramento_e_fonte(self):
        for sem in intervalo("2022.1", "2026.1"):
            self.assertIn(sem, self.cal)
            self.assertTrue(self.cal[sem]["fonte_url"].startswith("https://"))

    def test_encerramento_e_a_data_mais_tardia(self):
        # 2022.1: último dia letivo 28/09/2022, aulas de reposição até 09/10/2022
        self.assertEqual(self.cal[(2022, 1)]["encerramento"], date(2022, 10, 9))
        # 2025.1: consolidação das turmas até 05/08/2025, depois do último dia letivo
        self.assertEqual(self.cal[(2025, 1)]["encerramento"], date(2025, 8, 5))

    def test_encerrado_so_depois_do_encerramento(self):
        self.assertFalse(encerrado_em(self.cal, 2026, 1, date(2026, 7, 23)))
        self.assertTrue(encerrado_em(self.cal, 2026, 1, date(2026, 7, 24)))
        self.assertFalse(encerrado_em(self.cal, 2026, 2, date(2026, 9, 28)))

    def test_semestre_fora_do_calendario_e_recusado(self):
        with self.assertRaises(KeyError):
            encerrado_em(self.cal, 2021, 1, date(2026, 9, 28))


def _pagina(linhas: list[tuple[str, list[str]]], total: int | None = None) -> BeautifulSoup:
    """HTML mínimo com a estrutura que o coletor espera da página de turmas
    do curso: um <div> com o link da disciplina seguido de table#table_lt."""
    partes = []
    for disciplina, celulas in linhas:
        tds = "".join(f"<td>{c}</td>" for c in celulas)
        partes.append(f'<div><a href="#">{disciplina}</a></div><table id="table_lt"><tr>{tds}</tr></table>')
    rodape = f"<p>{total} Turmas Disponíveis</p>" if total is not None else ""
    return BeautifulSoup("<html><body>" + "".join(partes) + rodape + "</body></html>", "html.parser")


class TestColetor(unittest.TestCase):
    def test_extrai_no_formato_do_loader(self):
        soup = _pagina([("MAT0025 - CÁLCULO 1", ["2022.1", "01", "FULANO", "2", "235M12"])], total=1)
        [linha] = extrair(soup, "FGA_SOFT", "2022.1", "url", "2026-09-28T13:00:00Z")
        self.assertEqual(list(linha), CAMPOS)
        self.assertEqual((linha["ano"], linha["periodo"], linha["vagas_reservadas"]), ("2022", "1", 2))

    def test_semestre_divergente_interrompe(self):
        soup = _pagina([("MAT0025 - CÁLCULO 1", ["2023.1", "01", "FULANO", "2", "235M12"])])
        with self.assertRaises(ValueError):
            extrair(soup, "FGA_SOFT", "2022.1", "url", "x")

    def test_total_anunciado_diferente_interrompe(self):
        soup = _pagina([("MAT0025 - CÁLCULO 1", ["2022.1", "01", "FULANO", "2", "235M12"])], total=2)
        with self.assertRaises(ValueError):
            extrair(soup, "FGA_SOFT", "2022.1", "url", "x")

    def test_consulta_vazia_interrompe(self):
        with self.assertRaises(ValueError):
            extrair(_pagina([]), "FGA_SOFT", "2022.1", "url", "x")

    def test_consolidar_reproduz_o_lote_versionado(self):
        """Separar o ofertas_por_curso.csv do lote por curso e semestre e
        consolidar de novo tem de devolver as mesmas linhas e colunas."""
        lote = Path(__file__).resolve().parents[2] / "data" / "coleta_publica_2026-09-28"
        original = lote / "ofertas_por_curso.csv"
        if not original.exists():
            self.skipTest("lote versionado não montado")
        with original.open(encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
        with tempfile.TemporaryDirectory() as tmp:
            partes = Path(tmp) / "partes"
            partes.mkdir()
            grupos: dict[str, list[dict]] = {}
            for r in linhas:
                grupos.setdefault(f"{r['curso_codigo']}_{r['ano']}_{r['periodo']}", []).append(r)
            for nome, grupo in grupos.items():
                with (partes / f"{nome}.csv").open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=CAMPOS)
                    w.writeheader()
                    w.writerows(grupo)
            saida = consolidar(partes, Path(tmp) / "novo")
            with saida.open(encoding="utf-8", newline="") as f:
                leitor = csv.DictReader(f)
                self.assertEqual(leitor.fieldnames, list(linhas[0]))
                novas = list(leitor)
        chave = lambda r: tuple(r.values())  # noqa: E731
        self.assertEqual(sorted(novas, key=chave), sorted(linhas, key=chave))


if __name__ == "__main__":
    unittest.main()
