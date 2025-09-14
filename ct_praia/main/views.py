

def home(request):
    return render(request, "base.html")

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction

from .forms import SignupAlunoForm
from .models import Usuario, Inscricao

AUTO_LOGIN = True  # troque para False se quiser redirecionar pro login

def is_aluno(user):
    return user.is_authenticated and hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.ALUNO

@transaction.atomic
def signup_aluno(request):
    if request.method == "POST":
        form = SignupAlunoForm(request.POST)
        if form.is_valid():
            user = form.save()  # cria auth_user
            # cria o Perfil vinculado (OneToOne) como ALUNO
            Usuario.objects.create(user=user, tipo=Usuario.Tipo.ALUNO)

            if AUTO_LOGIN:
                raw_pw = form.cleaned_data["password1"]
                user = authenticate(username=user.username, password=raw_pw)
                if user:
                    login(request, user)
                    messages.success(request, "Cadastro realizado! Bem-vindo(a).")
                    return redirect("meus_treinos")
            messages.success(request, "Cadastro realizado! Faça login para continuar.")
            return redirect("login")
    else:
        form = SignupAlunoForm()
    return render(request, "registration/signup_aluno.html", {"form": form})

@user_passes_test(is_aluno, login_url="/accounts/login/")
def meus_treinos(request):
    inscricoes = (
        Inscricao.objects
        .select_related("treino", "treino__ct")
        .filter(aluno=request.user)
        .order_by("treino__data", "treino__hora_inicio")
    )
    return render(request, "aluno/meus_treinos.html", {"inscricoes": inscricoes})
