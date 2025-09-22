from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction

from .forms import SignupAlunoForm, SignupProfessorForm
from .models import Usuario, Inscricao

AUTO_LOGIN = True  # troque para False se quiser redirecionar pro login

def home(request):
    # Se autenticado, envia para o dashboard adequado
    if request.user.is_authenticated and hasattr(request.user, "usuario"):
        if request.user.usuario.tipo == Usuario.Tipo.ALUNO:
            return redirect("meus_treinos")
        if request.user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            return redirect("prof_dashboard")
    return render(request, "base.html")


def is_aluno(user):
    return user.is_authenticated and hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.ALUNO


def is_professor(user):
    return user.is_authenticated and hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.PROFESSOR

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


@transaction.atomic
def signup_professor(request):
    if request.method == "POST":
        form = SignupProfessorForm(request.POST)
        if form.is_valid():
            user = form.save()
            Usuario.objects.create(user=user, tipo=Usuario.Tipo.PROFESSOR)

            if AUTO_LOGIN:
                raw_pw = form.cleaned_data["password1"]
                user = authenticate(username=user.username, password=raw_pw)
                if user:
                    login(request, user)
                    messages.success(request, "Cadastro de professor realizado! Bem-vindo(a).")
                    return redirect("prof_dashboard")
            messages.success(request, "Cadastro de professor realizado! Faça login para continuar.")
            return redirect("login")
    else:
        form = SignupProfessorForm()
    return render(request, "registration/signup_professor.html", {"form": form})


@user_passes_test(is_professor, login_url="/accounts/login/")
def prof_dashboard(request):
    # Dashboard mínimo: lista de treinos que o professor ministra
    treinos = (
        request.user.treinos_ministrados.select_related("ct").order_by("data", "hora_inicio")
        if request.user.is_authenticated else []
    )
    return render(request, "professor/dashboard.html", {"treinos": treinos})

@user_passes_test(is_aluno, login_url="/accounts/login/")
def meus_treinos(request):
    inscricoes = (
        Inscricao.objects
        .select_related("treino", "treino__ct")
        .filter(aluno=request.user)
        .order_by("treino__data", "treino__hora_inicio")
    )
    return render(request, "aluno/meus_treinos.html", {"inscricoes": inscricoes})
