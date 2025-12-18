from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import (
	AgendamentoTreino,
	CentroTreinamento,
	HorarioRecorrente,
	Inscricao,
	ProfessorCentroTreinamento,
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


class PermissionsAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()

		self.gerente = User.objects.create_user("ger", "ger@example.com", "pass1234")
		Usuario.objects.create(user=self.gerente, tipo=Usuario.Tipo.GERENTE)

		self.professor = User.objects.create_user("prof2", "prof2@example.com", "pass1234")
		Usuario.objects.create(user=self.professor, tipo=Usuario.Tipo.PROFESSOR)

		self.aluno = User.objects.create_user("aluno", "aluno@example.com", "pass1234")
		Usuario.objects.create(user=self.aluno, tipo=Usuario.Tipo.ALUNO)

		self.ct = CentroTreinamento.objects.create(
			nome="CT Perm",
			endereco="Rua 2",
			contato="(11) 98888-8888",
			modalidades="Beach Tennis",
			cnpj="98.765.432/0001-10",
			gerente=self.gerente,
		)
		ProfessorCentroTreinamento.objects.create(ct=self.ct, professor=self.professor)

	def test_professor_cannot_create_treino_by_default(self):
		self.client.force_authenticate(user=self.professor)
		payload = {
			"ct": self.ct.id,
			"professor": self.professor.id,
			"modalidade": "Beach Tennis",
			"data": (date.today() + timedelta(days=1)).isoformat(),
			"hora_inicio": "06:00:00",
			"hora_fim": "07:00:00",
			"vagas": 10,
			"nivel": "Iniciante",
			"observacoes": "",
		}
		resp = self.client.post(reverse("treino-list"), payload, format="json")
		self.assertEqual(resp.status_code, 403)

	def test_gerente_can_create_treino_for_professor(self):
		self.client.force_authenticate(user=self.gerente)
		payload = {
			"ct": self.ct.id,
			"professor": self.professor.id,
			"modalidade": "Beach Tennis",
			"data": (date.today() + timedelta(days=1)).isoformat(),
			"hora_inicio": "06:00:00",
			"hora_fim": "07:00:00",
			"vagas": 10,
			"nivel": "Iniciante",
			"observacoes": "",
		}
		resp = self.client.post(reverse("treino-list"), payload, format="json")
		self.assertEqual(resp.status_code, 201)

	def test_gerente_can_grant_professor_create_and_professor_can_create(self):
		self.client.force_authenticate(user=self.gerente)
		vinculo = ProfessorCentroTreinamento.objects.get(ct=self.ct, professor=self.professor)
		resp = self.client.patch(
			reverse("professor_ct-detail", args=[vinculo.id]),
			{"pode_criar_treino": True},
			format="json",
		)
		self.assertEqual(resp.status_code, 200)

		self.client.force_authenticate(user=self.professor)
		payload = {
			"ct": self.ct.id,
			"professor": self.professor.id,
			"modalidade": "Beach Tennis",
			"data": (date.today() + timedelta(days=2)).isoformat(),
			"hora_inicio": "08:00:00",
			"hora_fim": "09:00:00",
			"vagas": 10,
			"nivel": "Iniciante",
			"observacoes": "",
		}
		resp2 = self.client.post(reverse("treino-list"), payload, format="json")
		self.assertEqual(resp2.status_code, 201)

	def test_professor_cannot_delete_agendamento_without_cancel_flag(self):
		# gerente cria agendamento apontando para professor
		self.client.force_authenticate(user=self.gerente)
		payload = {
			"ct": self.ct.id,
			"professor": self.professor.id,
			"modalidade": "Beach Tennis",
			"vagas": 10,
			"nivel": "Iniciante",
			"observacoes": "",
			"horarios": [{"dia_semana": 0, "hora_inicio": "06:00:00", "hora_fim": "07:00:00"}],
		}
		resp = self.client.post(reverse("agendamento-list"), payload, format="json")
		self.assertEqual(resp.status_code, 201)
		agendamento_id = resp.data["id"]

		# professor tenta deletar sem permissão
		self.client.force_authenticate(user=self.professor)
		resp2 = self.client.delete(reverse("agendamento-detail", args=[agendamento_id]))
		self.assertEqual(resp2.status_code, 403)

		# gerente concede cancelamento
		self.client.force_authenticate(user=self.gerente)
		vinculo = ProfessorCentroTreinamento.objects.get(ct=self.ct, professor=self.professor)
		self.client.patch(
			reverse("professor_ct-detail", args=[vinculo.id]),
			{"pode_cancelar_treino": True},
			format="json",
		)

		# agora professor pode deletar
		self.client.force_authenticate(user=self.professor)
		resp3 = self.client.delete(reverse("agendamento-detail", args=[agendamento_id]))
		self.assertEqual(resp3.status_code, 204)

	def test_inscricao_cancel_only_by_owner(self):
		# gerente cria um treino futuro
		self.client.force_authenticate(user=self.gerente)
		treino_resp = self.client.post(
			reverse("treino-list"),
			{
				"ct": self.ct.id,
				"professor": self.professor.id,
				"modalidade": "Beach Tennis",
				"data": (date.today() + timedelta(days=1)).isoformat(),
				"hora_inicio": "06:00:00",
				"hora_fim": "07:00:00",
				"vagas": 10,
				"nivel": "Iniciante",
				"observacoes": "",
			},
			format="json",
		)
		self.assertEqual(treino_resp.status_code, 201)
		treino_id = treino_resp.data["id"]

		# aluno cria inscrição
		self.client.force_authenticate(user=self.aluno)
		insc_resp = self.client.post(reverse("inscricao-list"), {"treino": treino_id}, format="json")
		self.assertEqual(insc_resp.status_code, 201)
		inscricao_id = insc_resp.data["id"]

		# gerente tenta cancelar inscrição (não deve)
		self.client.force_authenticate(user=self.gerente)
		resp2 = self.client.post(reverse("inscricao-cancelar", args=[inscricao_id]))
		self.assertEqual(resp2.status_code, 403)