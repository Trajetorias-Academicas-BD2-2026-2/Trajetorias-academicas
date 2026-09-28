"""Testes da interpretação do SIGAA e das regras de semestre.

    docker compose run --rm loader python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsing import (  # noqa: E402
    codigos_da_expressao,
    extrair_expressao_prerequisito,
    extrair_horario,
    inferir_turno,
    parse_vagas,
)
from semestres import encerrado, intervalo, parse_semestre, semestre_corrente  # noqa: E402


class TestHorarioETurno(unittest.TestCase):
    def test_horario_ignora_datas_e_nome_do_docente(self):
        # Nomes com M/T/N não podem ser confundidos com horário.
        celulas = ["01", "2026.1", "MARTA NUNES (60h)", "35T23 (09/03/2026 - 11/07/2026)", "40", "38", "S1"]
        self.assertEqual(extrair_horario(celulas), "35T23")

    def test_horario_com_mais_de_um_bloco(self):
        self.assertEqual(extrair_horario(["01", "24M12 6T34"]), "24M12 6T34")

    def test_turma_sem_horario(self):
        self.assertEqual(extrair_horario(["01", "FULANO", "A definir"]), "")
        self.assertEqual(inferir_turno(""), "SEM_HORARIO")

    def test_turnos(self):
        self.assertEqual(inferir_turno("246M12"), "DIURNO")
        self.assertEqual(inferir_turno("24M12 6T34"), "DIURNO")
        self.assertEqual(inferir_turno("35N12"), "NOTURNO")
        self.assertEqual(inferir_turno("2T45 4N12"), "INTEGRAL")


class TestVagas(unittest.TestCase):
    def test_ocupacao_acima_da_oferta_nao_e_trocada(self):
        self.assertEqual(parse_vagas(["01", "FULANO", "35T23", "40", "47", "S1"]), (40, 47))

    def test_codigo_de_turma_numerico_nao_conta_como_vaga(self):
        self.assertEqual(parse_vagas(["01", "FULANO", "35T23", "40", "S1"]), (None, None))

    def test_sem_numeros(self):
        self.assertEqual(parse_vagas(["A", "FULANO"]), (None, None))


class TestPreRequisito(unittest.TestCase):
    PAGINA = (
        "Código: FGA0003\nNome: CÁLCULO 3\n"
        "Pré-Requisitos: ( FGA0001 E FGA0002 )\n OU ( MAT0025 )\n"
        "Co-Requisitos: -\nEmenta: ..."
    )

    def test_expressao_multilinha_ate_o_proximo_rotulo(self):
        self.assertEqual(
            extrair_expressao_prerequisito(self.PAGINA),
            "( FGA0001 E FGA0002 ) OU ( MAT0025 )",
        )

    def test_codigos_sem_repeticao(self):
        self.assertEqual(
            codigos_da_expressao("( FGA0001 E FGA0002 ) OU ( FGA0001 E MAT0025 )"),
            ["FGA0001", "FGA0002", "MAT0025"],
        )

    def test_sem_prerequisito(self):
        self.assertEqual(extrair_expressao_prerequisito("Pré-Requisitos: -\nEmenta: x"), "")
        self.assertEqual(extrair_expressao_prerequisito("Ementa: x"), "")


class TestSemestres(unittest.TestCase):
    def test_intervalo(self):
        s = intervalo("2022.1", "2026.1")
        self.assertEqual(len(s), 9)
        self.assertEqual(s[0], (2022, 1))
        self.assertEqual(s[-1], (2026, 1))

    def test_periodo_invalido(self):
        with self.assertRaises(ValueError):
            parse_semestre("2024.3")

    def test_semestre_corrente(self):
        self.assertEqual(semestre_corrente(date(2026, 9, 28)), (2026, 2))
        self.assertEqual(semestre_corrente(date(2027, 1, 15)), (2026, 2))
        self.assertEqual(semestre_corrente(date(2027, 4, 1)), (2027, 1))

    def test_so_semestres_encerrados(self):
        hoje = date(2026, 9, 28)
        self.assertTrue(encerrado(2026, 1, hoje))
        self.assertFalse(encerrado(2026, 2, hoje))


if __name__ == "__main__":
    unittest.main()
