from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Usuario


def role_required(*allowed_tipos: str):
    """Decorator to restrict a view to specific Usuario tipos.

    Usage:
        @role_required(Usuario.Tipo.ALUNO)
        def view(...):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            # Must have associated Usuario profile and be an allowed tipo
            if not hasattr(user, "usuario"):
                # Usuário autenticado mas sem perfil: envia para home genérica
                return redirect("home")
            if user.usuario.tipo not in allowed_tipos:
                # Redireciona para a landing do seu perfil
                if user.usuario.tipo == Usuario.Tipo.ALUNO:
                    return redirect("meus_treinos")
                if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
                    return redirect("prof_dashboard")
                return redirect("home")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Shortcuts
aluno_required = role_required(Usuario.Tipo.ALUNO)
professor_required = role_required(Usuario.Tipo.PROFESSOR)
