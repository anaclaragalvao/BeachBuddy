from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.urls import reverse_lazy

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import CentroTreinamento, Treino
from .forms import CentroTreinamentoForm, TreinoForm, UsuarioProfileForm, CTProfessoresForm
from .mixins import ProfOrManagerRequiredMixin, ProfessorRequiredMixin

from .forms import SignupAlunoForm, SignupProfessorForm, SignupGerenteForm
from .models import Usuario, Inscricao
from .decorators import aluno_required, professor_required

AUTO_LOGIN = True  # troque para False se quiser redirecionar pro login

def home(request):
    """Landing: redireciona usuários autenticados conforme o perfil; exibe métricas se anônimo."""
    if request.user.is_authenticated and hasattr(request.user, "usuario"):
        tipo = request.user.usuario.tipo
        if tipo == Usuario.Tipo.ALUNO:
            return redirect("meus_treinos")
        if tipo == Usuario.Tipo.PROFESSOR:
            return redirect("prof_dashboard")
        if tipo == Usuario.Tipo.GERENTE:
            return redirect("meus_cts")


    # Métricas simples para a landing
    metric_cts = CentroTreinamento.objects.count()
    metric_professores = Usuario.objects.filter(tipo=Usuario.Tipo.PROFESSOR).count()
    # Treinos futuros
    now = timezone.localdate()
    metric_treinos = Treino.objects.filter(data__gte=now).count()
    metric_alunos = Usuario.objects.filter(tipo=Usuario.Tipo.ALUNO).count()

    context = {
        "metric_cts": metric_cts,
        "metric_professores": metric_professores,
        "metric_treinos": metric_treinos,
        "metric_alunos": metric_alunos,
    }
    return render(request, "home.html", context)


def is_aluno(user):
    return user.is_authenticated and hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.ALUNO


def is_professor(user):
    return user.is_authenticated and hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.PROFESSOR

def is_prof_or_manager(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, "usuario") and user.usuario.tipo in (Usuario.Tipo.PROFESSOR, Usuario.Tipo.GERENTE)

@transaction.atomic
def signup_aluno(request):
    """Cadastro de aluno com criação de perfil Usuario e opção de auto login."""
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
    """Cadastro de professor; cria perfil Usuario (PROFESSOR) e auto login opcional."""
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


@transaction.atomic
def signup_gerente(request):
    """Cadastro de gerente; cria perfil Usuario (GERENTE) e redireciona para gestão de CTs."""
    if request.method == "POST":
        form = SignupGerenteForm(request.POST)
        if form.is_valid():
            user = form.save()
            Usuario.objects.create(user=user, tipo=Usuario.Tipo.GERENTE)

            if AUTO_LOGIN:
                raw_pw = form.cleaned_data["password1"]
                user = authenticate(username=user.username, password=raw_pw)
                if user:
                    login(request, user)
                    messages.success(request, "Cadastro de gerente realizado! Bem-vindo(a).")
                    return redirect("meus_cts")
            messages.success(request, "Cadastro de gerente realizado! Faça login para continuar.")
            return redirect("login")
    else:
        form = SignupGerenteForm()
    return render(request, "registration/signup_gerente.html", {"form": form})


@professor_required
def prof_dashboard(request):
    """Dashboard do professor: lista treinos futuros, cria/edita/exclui (modo modal) e mostra métricas."""
    base_qs = (
        request.user.treinos_ministrados.select_related("ct")
        .annotate(
            confirmadas=Count(
                "inscricoes",
                filter=Q(inscricoes__status=Inscricao.Status.CONFIRMADA),
            )
        )
    )
    form = TreinoForm(user=request.user)
    show_treino_modal = False
    modal_mode = "create"
    editing_treino_id = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_treino":
            form = TreinoForm(request.POST, user=request.user)
            if form.is_valid():
                treino = form.save(commit=False)
                treino.professor = request.user
                data = form.cleaned_data.get("data")
                ct = form.cleaned_data.get("ct")
                hi = form.cleaned_data.get("hora_inicio")
                hf = form.cleaned_data.get("hora_fim")
                conflict = False
                if data and ct and hi and hf:
                    conflict = Treino.objects.filter(
                        professor=request.user,
                        ct=ct,
                        data=data,
                        hora_inicio__lt=hf,
                        hora_fim__gt=hi,
                    ).exists()
                if conflict:
                    form.add_error(None, "Conflito de horário com outro treino seu neste CT.")
                    show_treino_modal = True
                    modal_mode = "create"
                else:
                    treino.save()
                    return redirect("prof_dashboard")
            else:
                show_treino_modal = True
                modal_mode = "create"
        elif action == "update_treino":
            treino_id = request.POST.get("treino_id")
            treino_obj = get_object_or_404(Treino, pk=treino_id, professor=request.user)
            form = TreinoForm(request.POST, user=request.user, instance=treino_obj)
            if form.is_valid():
                data = form.cleaned_data.get("data")
                ct = form.cleaned_data.get("ct")
                hi = form.cleaned_data.get("hora_inicio")
                hf = form.cleaned_data.get("hora_fim")
                conflict = False
                if data and ct and hi and hf:
                    conflict = Treino.objects.filter(
                        professor=request.user,
                        ct=ct,
                        data=data,
                        hora_inicio__lt=hf,
                        hora_fim__gt=hi,
                    ).exclude(pk=treino_obj.pk).exists()
                if conflict:
                    form.add_error(None, "Conflito de horário com outro treino seu neste CT.")
                    show_treino_modal = True
                    modal_mode = "edit"
                    editing_treino_id = treino_obj.pk
                else:
                    form.save()
                    return redirect("prof_dashboard")
            else:
                show_treino_modal = True
                modal_mode = "edit"
                editing_treino_id = treino_obj.pk
        elif action == "delete_treino":
            treino_id = request.POST.get("treino_id")
            if not treino_id:
                messages.error(request, "Treino inválido para exclusão.")
                return redirect("prof_dashboard")
            try:
                treino_obj = Treino.objects.get(pk=treino_id, professor=request.user)
            except Treino.DoesNotExist:
                messages.error(request, "Não encontramos esse treino para excluir.")
            else:
                treino_obj.delete()
            return redirect("prof_dashboard")

    now = timezone.localtime()
    upcoming_filter = Q(data__gt=now.date()) | (Q(data=now.date()) & Q(hora_fim__gte=now.time()))
    base_upcoming_qs = base_qs.filter(upcoming_filter)
    qs = base_upcoming_qs.order_by("data", "hora_inicio")

    selected_date = request.GET.get("data", "")
    raw_ct = request.GET.get("ct", "")
    selected_period = request.GET.get("period", "").lower()
    if selected_period not in {"today", "week", "month"}:
        selected_period = ""

    selected_ct = None

    if raw_ct:
        try:
            selected_ct = int(raw_ct)
            qs = qs.filter(ct_id=selected_ct)
        except (TypeError, ValueError):
            selected_ct = None

    if selected_period:
        if selected_period == "today":
            qs = qs.filter(data=now.date())
        elif selected_period == "week":
            qs = qs.filter(data__range=(now.date(), now.date() + timedelta(days=7)))
        elif selected_period == "month":
            qs = qs.filter(data__range=(now.date(), now.date() + timedelta(days=30)))
        selected_date = ""
    elif selected_date:
        qs = qs.filter(data=selected_date)

    qs = qs.order_by("data", "hora_inicio")
    treinos = list(qs)
    for treino in treinos:
        confirmadas = getattr(treino, "confirmadas", 0) or 0
        treino.vagas_disponiveis = max(treino.vagas - confirmadas, 0)
    total_treinos = len(treinos)
    metrics_source = base_upcoming_qs
    if selected_ct:
        metrics_source = metrics_source.filter(ct_id=selected_ct)
    treinos_hoje = metrics_source.filter(data=now.date()).count()
    treinos_semana = metrics_source.filter(
        data__range=(now.date(), now.date() + timedelta(days=7))
    ).count()
    treinos_mes = metrics_source.filter(
        data__range=(now.date(), now.date() + timedelta(days=30))
    ).count()

    next_treino_alunos = 0
    next_treino = qs.first()
    if next_treino:
        next_treino_alunos = next_treino.inscricoes.filter(status=Inscricao.Status.CONFIRMADA).count()

    cts = request.user.cts_associados.order_by("nome")
    context = {
        "treinos": treinos,
        "cts": cts,
        "selected_date": selected_date,
        "selected_ct": selected_ct,
        "selected_period": selected_period,
        "total_treinos": total_treinos,
        "next_treino": next_treino,
        "next_treino_alunos": next_treino_alunos,
        "treinos_hoje": treinos_hoje,
        "treinos_semana": treinos_semana,
        "treinos_mes": treinos_mes,
        "treino_form": form,
        "show_treino_modal": show_treino_modal,
        "modal_mode": modal_mode,
        "editing_treino_id": editing_treino_id,
    }
    return render(request, "professor/dashboard.html", context)

@aluno_required
def meus_treinos(request):
    """Lista inscrições futuras do aluno (exclui canceladas) ordenadas cronologicamente."""
    now = timezone.localtime()
    upcoming_filter = Q(treino__data__gt=now.date()) | (
        Q(treino__data=now.date()) & Q(treino__hora_fim__gte=now.time())
    )
    inscricoes = (
        Inscricao.objects
        .select_related("treino", "treino__ct")
        .filter(aluno=request.user)
        .exclude(status=Inscricao.Status.CANCELADA)
        .filter(upcoming_filter)
        .order_by("treino__data", "treino__hora_inicio")
    )
    return render(request, "aluno/meus_treinos.html", {"inscricoes": inscricoes})


# --- Inscrições (Aluno) ---
@aluno_required
def inscricao_criar(request, treino_id: int):
    """Cria ou reativa inscrição (CONFIRMADA) respeitando limite de vagas; bloqueia se lotado."""
    if request.method != "POST":
        return redirect("meus_treinos")
    treino = get_object_or_404(Treino, pk=treino_id)
    # Verifica capacidade (inscrições confirmadas)
    confirmadas = Inscricao.objects.filter(
        treino=treino, status=Inscricao.Status.CONFIRMADA
    ).count()

    insc = Inscricao.objects.filter(treino=treino, aluno=request.user).first()
    if insc:
        if insc.status == Inscricao.Status.CANCELADA:
            if confirmadas >= treino.vagas:
                messages.error(request, "Treino lotado. Não foi possível reativar a inscrição.")
                return redirect("meus_treinos")
            insc.status = Inscricao.Status.CONFIRMADA
            insc.save(update_fields=["status"])
    else:
        if confirmadas >= treino.vagas:
            messages.error(request, "Treino lotado. Não foi possível realizar a inscrição.")
            return redirect("meus_treinos")
        Inscricao.objects.create(
            treino=treino, aluno=request.user, status=Inscricao.Status.CONFIRMADA
        )
    return redirect("meus_treinos")


@aluno_required
def inscricao_cancelar(request, pk: int):
    """Cancela (marca como CANCELADA) a inscrição do aluno se não estiver já cancelada."""
    if request.method != "POST":
        return redirect("meus_treinos")
    insc = get_object_or_404(Inscricao, pk=pk, aluno=request.user)
    if insc.status != Inscricao.Status.CANCELADA:
        insc.status = Inscricao.Status.CANCELADA
        insc.save(update_fields=["status"])
    return redirect("meus_treinos")


@aluno_required
def novo_treino_escolher_ct(request):
    """Passo 1 do fluxo de inscrição: exibe CTs para o aluno escolher."""
    cts = CentroTreinamento.objects.all().order_by("nome")
    return render(request, "aluno/novo_treino_escolher_ct.html", {"cts": cts})


@aluno_required
def novo_treino_escolher_treino(request, ct_id: int):
    """Passo 2: lista treinos futuros do CT com contagem de confirmadas e marca os já inscritos."""
    ct = get_object_or_404(CentroTreinamento, pk=ct_id)
    today = timezone.localdate()
    treinos = (
        Treino.objects.filter(ct=ct, data__gte=today)
        .select_related("ct", "professor")
        .annotate(confirmadas=Count("inscricoes", filter=Q(inscricoes__status=Inscricao.Status.CONFIRMADA)))
        .order_by("data", "hora_inicio")
    )
    inscritos_ids = (
        Inscricao.objects.filter(
            aluno=request.user, status__in=[Inscricao.Status.PENDENTE, Inscricao.Status.CONFIRMADA]
        ).values_list("treino_id", flat=True)
    )
    context = {
        "ct": ct,
        "treinos": treinos,
        "inscritos_ids": list(inscritos_ids),
    }
    return render(request, "aluno/novo_treino_escolher_treino.html", context)

class CTListView(ListView):
    """Lista geral de CTs com anotações (treinos futuros, total de professores) e filtro por perfil."""
    model = CentroTreinamento
    template_name = "ct/ct_list.html"
    context_object_name = "cts"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("gerente")
            .prefetch_related("professores")
        )
        today = timezone.localdate()
        qs = qs.annotate(
            upcoming_treinos=Count(
                "treinos",
                filter=Q(treinos__data__gte=today),
                distinct=True,
            ),
            professores_total=Count("professores", distinct=True),
        )

        user = self.request.user
        if user.is_authenticated and hasattr(user, "usuario"):
            if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
                qs = qs.filter(professores=user)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["is_professor"] = (
            user.is_authenticated
            and hasattr(user, "usuario")
            and user.usuario.tipo == Usuario.Tipo.PROFESSOR
        )
        ctx["is_gerente"] = (
            user.is_authenticated
            and hasattr(user, "usuario")
            and user.usuario.tipo == Usuario.Tipo.GERENTE
        )
        return ctx

class CTDetailView(DetailView):
    """Detalhe de um CT: professores, próximos treinos (ou todos), métricas simples e marca inscrições do usuário."""
    model = CentroTreinamento
    template_name = "ct/ct_detail.html"
    context_object_name = "ct"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        mostrar_todos = self.request.GET.get("all") == "1"
        base_qs = (
            self.object.treinos
            .select_related("ct", "professor")
            .annotate(confirmadas=Count("inscricoes", filter=Q(inscricoes__status=Inscricao.Status.CONFIRMADA)))
        )

        futuros_qs = base_qs.filter(data__gte=today)
        proximos_count = futuros_qs.count()
        proximos_proximo = futuros_qs.order_by("data", "hora_inicio").first()
        passados_count = base_qs.filter(data__lt=today).count()

        qs = futuros_qs if not mostrar_todos else base_qs
        treinos = qs.order_by("data", "hora_inicio")

        ctx["treinos"] = list(treinos)
        ctx["mostrar_todos"] = mostrar_todos
        ctx["proximos_count"] = proximos_count
        ctx["passados_count"] = passados_count
        ctx["next_treino"] = proximos_proximo
        ctx["professores"] = list(
            self.object.professores.order_by("first_name", "last_name", "username")
        )
        if self.request.user.is_authenticated:
            inscritos_ids = Inscricao.objects.filter(
                aluno=self.request.user,
                status__in=[Inscricao.Status.PENDENTE, Inscricao.Status.CONFIRMADA],
            ).values_list("treino_id", flat=True)
            ctx["inscritos_ids"] = list(inscritos_ids)
        else:
            ctx["inscritos_ids"] = []
        return ctx

class CTCreateView(ProfOrManagerRequiredMixin, CreateView):
    """Criação de CT por professor (genérico) ou gerente; gerente vira responsável automaticamente."""
    model = CentroTreinamento
    form_class = CentroTreinamentoForm
    template_name = "ct/ct_form.html"
    success_url = reverse_lazy("ct_list")

    def form_valid(self, form):
        # Se usuário for gerente, define como gerente do CT
        user = self.request.user
        if hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.GERENTE:
            form.instance.gerente = user
        return super().form_valid(form)

class CTUpdateView(ProfOrManagerRequiredMixin, UpdateView):
    """Edição de CT limitada ao gerente ou superuser; professores não gerentes não podem alterar outros CTs."""
    model = CentroTreinamento
    form_class = CentroTreinamentoForm
    template_name = "ct/ct_form.html"
    success_url = reverse_lazy("ct_list")
    
    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.is_superuser:
            return qs
        if hasattr(u, "usuario") and u.usuario.tipo == Usuario.Tipo.GERENTE:
            return qs.filter(gerente=u)
        return qs

class CTDeleteView(ProfOrManagerRequiredMixin, DeleteView):
    """Exclusão de CT (apenas gerente do CT ou superuser)."""
    model = CentroTreinamento
    template_name = "ct/ct_confirm_delete.html"
    success_url = reverse_lazy("ct_list")


# --- Treino CRUD (Professor) ---
class TreinoListView(ProfessorRequiredMixin, ListView):
    """Lista treinos (contextual: filtrável no template)  restrito a professor/superuser."""
    model = Treino
    template_name = "professor/treino_list.html"
    context_object_name = "treinos"

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.is_superuser:
            return qs
        if hasattr(u, "usuario") and u.usuario.tipo == Usuario.Tipo.GERENTE:
            return qs.filter(gerente=u)
        return qs


# --- Gerente: meus CTs ---
@login_required
def gerente_meus_cts(request):
    """Dashboard simples do gerente: lista CTs sob sua gestão com métricas agregadas (treinos futuros/professores)."""
    if not hasattr(request.user, "usuario") or request.user.usuario.tipo != Usuario.Tipo.GERENTE:
        # Redireciona conforme perfil
        return redirect("home")
    today = timezone.localdate()
    cts = (
        CentroTreinamento.objects
        .filter(gerente=request.user)
        .annotate(
            treinos_futuros=Count(
                "treinos",
                filter=Q(treinos__data__gte=today),
            )
        )
        .prefetch_related("professores")
        .order_by("nome")
    )
    total_cts = cts.count()
    UserModel = get_user_model()
    total_professores = (
        UserModel.objects
        .filter(cts_associados__gerente=request.user)
        .distinct()
        .count()
    )
    total_treinos = Treino.objects.filter(ct__gerente=request.user, data__gte=today).count()
    context = {
        "cts": cts,
        "total_cts": total_cts,
        "total_professores": total_professores,
        "total_treinos": total_treinos,
    }
    return render(request, "gerente/meus_cts.html", context)




@login_required
def gerente_ct_professores(request, pk: int):
    """Permite ao gerente gerenciar o conjunto de professores associados ao CT."""
    if not hasattr(request.user, "usuario") or request.user.usuario.tipo != Usuario.Tipo.GERENTE:
        return redirect("home")
    ct = get_object_or_404(CentroTreinamento, pk=pk, gerente=request.user)
    if request.method == "POST":
        form = CTProfessoresForm(request.POST, instance=ct, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Professores atualizados para o CT.")
            return redirect("meus_cts")
    else:
        form = CTProfessoresForm(instance=ct, user=request.user)
    # Mostrar também professores já associados e potencialmente contagem de treinos
    professores = ct.professores.all().order_by("username")
    return render(request, "gerente/ct_professores.html", {"ct": ct, "form": form, "professores": professores})


class GerenteCTCreateView(CreateView):
    """Criação de CT via fluxo específico do gerente (define gerente automaticamente)."""
    model = CentroTreinamento
    form_class = CentroTreinamentoForm
    template_name = "gerente/novo_ct.html"
    success_url = reverse_lazy("meus_cts")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not hasattr(request.user, "usuario") or request.user.usuario.tipo != Usuario.Tipo.GERENTE:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.gerente = self.request.user
        return super().form_valid(form)


# --- Treino CRUD (Professor) ---
class TreinoCreateView(ProfessorRequiredMixin, CreateView):
    """Criação de treino (professor): valida conflito de horário e associação ao CT."""
    model = Treino
    form_class = TreinoForm
    template_name = "professor/treino_form.html"
    success_url = reverse_lazy("prof_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.professor = self.request.user
        # Revalida associação professor-CT (Treino.clean e form.clean_ct)
        form.instance.full_clean(exclude=None)
        # validação de conflito de horário para mesmo professor e mesmo CT na mesma data
        data = form.cleaned_data.get("data")
        ct = form.cleaned_data.get("ct")
        hi = form.cleaned_data.get("hora_inicio")
        hf = form.cleaned_data.get("hora_fim")
        if data and ct and hi and hf:
            overlap = Treino.objects.filter(
                professor=self.request.user,
                ct=ct,
                data=data,
                hora_inicio__lt=hf,
                hora_fim__gt=hi,
            ).exists()
            if overlap:
                form.add_error(None, "Conflito de horário com outro treino seu neste CT.")
                return self.form_invalid(form)
        return super().form_valid(form)


# --- Perfil (Aluno/Professor) ---
@login_required
def perfil_detail(request):
    """Exibe dados do perfil (Aluno/Professor) com lista formatada de certificações."""
    # Apenas Aluno/Professor (ou superuser) podem ver/editar o próprio perfil
    if not request.user.is_superuser:
        if not hasattr(request.user, "usuario") or request.user.usuario.tipo not in (
            Usuario.Tipo.ALUNO,
            Usuario.Tipo.PROFESSOR,
        ):
            return redirect("home")
    perfil = getattr(request.user, "usuario", None)
    display_name = request.user.get_full_name() or request.user.get_username()
    certificacoes_list = []
    if perfil and perfil.certificacoes:
        certificacoes_list = [
            item.strip()
            for item in perfil.certificacoes.splitlines()
            if item.strip()
        ]
    context = {
        "perfil": perfil,
        "display_name": display_name,
        "certificacoes_list": certificacoes_list,
    }
    return render(request, "perfil/perfil_detail.html", context)


@login_required
def perfil_editar(request):
    """Form de edição de perfil (Aluno/Professor); impede outros perfis não autorizados."""
    if not request.user.is_superuser:
        if not hasattr(request.user, "usuario") or request.user.usuario.tipo not in (
            Usuario.Tipo.ALUNO,
            Usuario.Tipo.PROFESSOR,
        ):
            return redirect("home")
    perfil = request.user.usuario
    if request.method == "POST":
        form = UsuarioProfileForm(request.POST, instance=perfil, usuario_tipo=perfil.tipo)
        if form.is_valid():
            form.save()
            return redirect("perfil_detail")
    else:
        form = UsuarioProfileForm(instance=perfil, usuario_tipo=perfil.tipo)
    return render(request, "perfil/perfil_form.html", {"form": form})
