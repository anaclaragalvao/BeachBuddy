from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
	AgendamentoTreino,
	CentroTreinamento,
	HorarioRecorrente,
	Treino,
	Usuario,
)
from .services import regenerate_agendamento_ocorrencias


User = get_user_model()


class AgendamentoServiceTests(TestCase):
	def setUp(self):
		self.professor = User.objects.create_user("prof", "prof@example.com", "pass1234")
		Usuario.objects.create(user=self.professor, tipo=Usuario.Tipo.PROFESSOR)
		self.ct = CentroTreinamento.objects.create(
			nome="CT Teste",
			endereco="Rua 1",
			contato="(11) 99999-9999",
			modalidades="Surf",
			cnpj="12.345.678/0001-90",
		)
		self.ct.professores.add(self.professor)
		self.agendamento = AgendamentoTreino.objects.create(
			ct=self.ct,
			professor=self.professor,
			modalidade="Surf",
			vagas=10,
			nivel="Iniciante",
			observacoes="",
		)
		HorarioRecorrente.objects.create(
			agendamento=self.agendamento,
			dia_semana=AgendamentoTreino.DiaSemana.SEGUNDA,
			hora_inicio=time(6, 0),
			hora_fim=time(7, 0),
		)

	def test_regenerate_creates_occurrences_inside_window(self):
		start = date(2024, 1, 1)  # Segunda-feira
		regenerate_agendamento_ocorrencias(self.agendamento, start_date=start, days_ahead=6)
		treinos = Treino.objects.filter(agendamento=self.agendamento).order_by("data")
		self.assertEqual(treinos.count(), 1)
		self.assertEqual(treinos[0].data, start)
		self.assertTrue(treinos[0].agendado)

	def test_regenerate_preserves_past_and_replaces_future(self):
		past_date = date(2023, 12, 25)  # Segunda
		Treino.objects.create(
			ct=self.ct,
			professor=self.professor,
			modalidade="Surf",
			data=past_date,
			hora_inicio=time(6, 0),
			hora_fim=time(7, 0),
			vagas=10,
			nivel="Iniciante",
			agendado=True,
			agendamento=self.agendamento,
		)
		start = date(2024, 1, 1)
		regenerate_agendamento_ocorrencias(self.agendamento, start_date=start, days_ahead=6)
		all_dates = list(Treino.objects.filter(agendamento=self.agendamento).values_list("data", flat=True))
		self.assertIn(past_date, all_dates)
		self.assertIn(start, all_dates)