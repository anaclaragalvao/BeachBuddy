from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Tuple

from django.db import transaction
from django.utils import timezone

from .models import AgendamentoTreino, HorarioRecorrente, Treino


DEFAULT_WINDOW_DAYS = 30


@dataclass(frozen=True)
class GenerationWindow:
    start: date
    end: date


def compute_generation_window(start_date: date | None = None, days_ahead: int = DEFAULT_WINDOW_DAYS) -> GenerationWindow:
    """Return the inclusive window used to materialize recurring trainings."""
    if start_date is None:
        start_date = timezone.localdate()
    if days_ahead < 0:
        raise ValueError("days_ahead deve ser positivo")
    end_date = start_date + timedelta(days=days_ahead)
    return GenerationWindow(start=start_date, end=end_date)


def regenerate_agendamento_ocorrencias(
    agendamento: AgendamentoTreino,
    start_date: date | None = None,
    days_ahead: int = DEFAULT_WINDOW_DAYS,
) -> int:
    """Recreate every future `Treino` generated from `agendamento` inside the window.

    Passado é mantido; apenas treinos a partir de `start_date` são recriados. Retorna
    quantas ocorrências foram criadas.
    """

    window = compute_generation_window(start_date=start_date, days_ahead=days_ahead)
    horarios: Iterable[HorarioRecorrente] = list(agendamento.horarios.all())
    if not horarios:
        return 0

    with transaction.atomic():
        Treino.objects.filter(agendamento=agendamento, data__gte=window.start).delete()

        created = 0
        total_days = (window.end - window.start).days + 1
        for offset in range(total_days):
            current_date = window.start + timedelta(days=offset)
            weekday = current_date.weekday()
            for horario in horarios:
                if horario.dia_semana != weekday:
                    continue
                Treino.objects.create(
                    ct=agendamento.ct,
                    professor=agendamento.professor,
                    modalidade=agendamento.modalidade,
                    data=current_date,
                    hora_inicio=horario.hora_inicio,
                    hora_fim=horario.hora_fim,
                    vagas=agendamento.vagas,
                    nivel=agendamento.nivel,
                    observacoes=agendamento.observacoes,
                    agendado=True,
                    agendamento=agendamento,
                )
                created += 1
    return created


def purge_future_treinos_beyond_window(days_ahead: int = DEFAULT_WINDOW_DAYS) -> int:
    """Remove recurring treinos that are beyond the allowed window."""
    window = compute_generation_window(days_ahead=days_ahead)
    deleted, _ = Treino.objects.filter(agendado=True, data__gt=window.end).delete()
    return deleted