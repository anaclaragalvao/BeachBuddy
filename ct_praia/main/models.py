from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Usuario(models.Model):
	"""Extensão de perfil para o usuário padrão do Django.

	Armazena o tipo de usuário sem trocar o AUTH_USER_MODEL.
	"""

	class Tipo(models.TextChoices):
		ALUNO = "ALUNO", "Aluno"
		PROFESSOR = "PROFESSOR", "Professor"
		GERENTE = "GERENTE", "Gerente"

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="usuario",
	)
	tipo = models.CharField(
		max_length=20,
		choices=Tipo.choices,
		default=Tipo.ALUNO,
	)

	# Campos de perfil básicos
	telefone = models.CharField(max_length=30, blank=True)
	nivel = models.CharField(max_length=50, blank=True, help_text="Ex.: Iniciante, Intermediário, Avançado")
	certificacoes = models.TextField(blank=True, help_text="Certificações (uma por linha ou texto livre)")

	def __str__(self) -> str:  # pragma: no cover - simples representação
		return f"{self.user.get_full_name() or self.user.username} ({self.get_tipo_display()})"


class CentroTreinamento(models.Model):
	nome = models.CharField(max_length=150)
	endereco = models.CharField(max_length=255)
	contato = models.CharField(max_length=100)
	modalidades = models.TextField(help_text="Modalidades oferecidas (texto livre)")
	cnpj = models.CharField(
		max_length=18,  # formato 00.000.000/0000-00
		unique=True,
		help_text="CNPJ do CT (com ou sem máscara)",
	)
	gerente = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="cts_gerenciados",
		null=True,
		blank=True,
		limit_choices_to={"usuario__tipo": Usuario.Tipo.GERENTE},
		help_text="Usuário gerente responsável pelo CT",
	)
	professores = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		blank=True,
		related_name="cts_associados",
		limit_choices_to={"usuario__tipo": Usuario.Tipo.PROFESSOR},
		help_text="Professores autorizados a ministrar treinos neste CT",
	)
	
	# Geolocalização para mapa
	latitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		help_text="Latitude da localização do CT (ex: -22.9068)"
	)
	longitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		help_text="Longitude da localização do CT (ex: -43.1729)"
	)

	class Meta:
		verbose_name = "Centro de Treinamento"
		verbose_name_plural = "Centros de Treinamento"
		ordering = ["nome"]

	def __str__(self) -> str:  # pragma: no cover
		return self.nome


class Treino(models.Model):
	ct = models.ForeignKey(
		CentroTreinamento,
		on_delete=models.CASCADE,
		related_name="treinos",
	)
	professor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="treinos_ministrados",
		limit_choices_to={"usuario__tipo": Usuario.Tipo.PROFESSOR},
	)
	modalidade = models.CharField(max_length=100)
	data = models.DateField()
	hora_inicio = models.TimeField()
	hora_fim = models.TimeField()
	vagas = models.PositiveIntegerField()
	nivel = models.CharField(max_length=50)
	observacoes = models.TextField(blank=True)

	class Meta:
		ordering = ["-data", "hora_inicio"]

	def clean(self):
		# hora_fim deve ser depois de hora_inicio
		if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
			raise ValidationError({"hora_fim": "Hora fim deve ser após a hora início."})

		# professor deve ter perfil de PROFESSOR
		usr = getattr(self, "professor", None)
		if usr and hasattr(usr, "usuario"):
			if usr.usuario.tipo != Usuario.Tipo.PROFESSOR:
				raise ValidationError({"professor": "Usuário selecionado não é um PROFESSOR."})

		# Professor deve estar associado ao CT selecionado
		if self.ct_id and self.professor_id:
			# Evita consulta se M2M não existe ainda em banco (objeto não salvo) -> usar through manager com exists
			if not self.ct.professores.filter(pk=self.professor_id).exists():
				raise ValidationError({"professor": "Professor não está associado a este CT."})

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.modalidade} - {self.data} ({self.ct})"


class Inscricao(models.Model):
	class Status(models.TextChoices):
		PENDENTE = "PENDENTE", "Pendente"
		CONFIRMADA = "CONFIRMADA", "Confirmada"
		CANCELADA = "CANCELADA", "Cancelada"

	treino = models.ForeignKey(
		Treino,
		on_delete=models.CASCADE,
		related_name="inscricoes",
	)
	aluno = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="inscricoes",
		limit_choices_to={"usuario__tipo": Usuario.Tipo.ALUNO},
	)
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.CONFIRMADA,
	)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("treino", "aluno")
		ordering = ["-criado_em"]

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.aluno} -> {self.treino} [{self.get_status_display()}]"

