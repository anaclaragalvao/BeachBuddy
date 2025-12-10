from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import (
	AgendamentoTreino,
	CentroTreinamento,
	HorarioRecorrente,
	Inscricao,
	Treino,
	Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
	list_display = ("user", "tipo")
	list_filter = ("tipo",)
	search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(CentroTreinamento)
class CentroTreinamentoAdmin(admin.ModelAdmin):
	list_display = ("nome", "gerente", "endereco", "contato")
	search_fields = ("nome", "endereco", "contato", "gerente__username")
	list_filter = ("gerente",)
	filter_horizontal = ("professores",)


@admin.register(Treino)
class TreinoAdmin(admin.ModelAdmin):
	list_display = (
		"modalidade",
		"ct",
		"professor",
		"data",
		"hora_inicio",
		"hora_fim",
		"vagas",
		"nivel",
		"agendado",
	)
	list_filter = ("ct", "modalidade", "data", "agendado")
	search_fields = ("modalidade", "ct__nome", "professor__username")
	autocomplete_fields = ("ct", "professor")


class HorarioRecorrenteInline(admin.TabularInline):
	model = HorarioRecorrente
	extra = 0


@admin.register(AgendamentoTreino)
class AgendamentoTreinoAdmin(admin.ModelAdmin):
	list_display = ("ct", "professor", "modalidade", "vagas", "nivel", "criado_em")
	search_fields = ("modalidade", "ct__nome", "professor__username")
	list_filter = ("ct", "professor")
	inlines = [HorarioRecorrenteInline]
	autocomplete_fields = ("ct", "professor")


@admin.register(Inscricao)
class InscricaoAdmin(admin.ModelAdmin):
	list_display = ("treino", "aluno", "status", "criado_em")
	list_filter = ("status", "treino__ct", "treino__modalidade")
	search_fields = ("treino__modalidade", "aluno__username")
	autocomplete_fields = ("treino", "aluno")


# Optionally re-register the default User with default UserAdmin
try:
	admin.site.unregister(get_user_model())
except admin.sites.NotRegistered:
	pass

@admin.register(get_user_model())
class _UserAdmin(UserAdmin):
	pass
