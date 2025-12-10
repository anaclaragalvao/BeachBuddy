from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import AgendamentoTreino
from ...services import (
    DEFAULT_WINDOW_DAYS,
    purge_future_treinos_beyond_window,
    regenerate_agendamento_ocorrencias,
)


class Command(BaseCommand):
    help = (
        "Gera ocorrências de treinos para todos os agendamentos ativos e remove "
        "ocorrências recorrentes que estejam além da janela permitida."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            dest="days_ahead",
            type=int,
            default=DEFAULT_WINDOW_DAYS,
            help="Quantidade de dias no futuro que devem permanecer disponíveis (default: 30).",
        )

    def handle(self, *args, **options):
        days_ahead = options["days_ahead"]
        today = timezone.localdate()

        purged = purge_future_treinos_beyond_window(days_ahead=days_ahead)
        if purged:
            self.stdout.write(self.style.WARNING(f"Removidos {purged} treinos além de {days_ahead} dias."))

        total_created = 0
        agendamentos = (
            AgendamentoTreino.objects
            .select_related("ct", "professor")
            .prefetch_related("horarios")
        )
        for agendamento in agendamentos:
            created = regenerate_agendamento_ocorrencias(
                agendamento,
                start_date=today,
                days_ahead=days_ahead,
            )
            total_created += created
            self.stdout.write(
                self.style.SUCCESS(
                    f"Agendamento {agendamento.pk}: {created} ocorrências recriadas."
                )
            )

        if total_created == 0 and purged == 0:
            self.stdout.write("Nenhuma alteração necessária.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Total de ocorrências criadas: {total_created}"))
