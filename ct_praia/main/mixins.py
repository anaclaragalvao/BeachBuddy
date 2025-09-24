from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Usuario

class ProfOrManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/accounts/login/"

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        return hasattr(u, "usuario") and u.usuario.tipo in (Usuario.Tipo.PROFESSOR, Usuario.Tipo.GERENTE)


class ProfessorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/accounts/login/"

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        return hasattr(u, "usuario") and u.usuario.tipo == Usuario.Tipo.PROFESSOR
