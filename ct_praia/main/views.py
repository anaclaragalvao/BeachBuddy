from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import user_passes_test
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
from django.contrib.auth.decorators import login_required

AUTO_LOGIN = True  # troque para False se quiser redirecionar pro login

def home(request):
    # Redireciona usuários logados para seus fluxos principais
    if request.user.is_authenticated and hasattr(request.user, "usuario"):
        if request.user.usuario.tipo == Usuario.Tipo.ALUNO:
            return redirect("meus_treinos")
        if request.user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            return redirect("prof_dashboard")

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

@transaction.atomic
def signup_gerente(request):
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
                    return redirect("prof_dashboard")
            messages.success(request, "Cadastro de gerente realizado! Faça login para continuar.")
            return redirect("login")
    else:
        form = SignupGerenteForm()
    return render(request, "registration/signup_gerente.html", {"form": form})


@professor_required
def prof_dashboard(request):
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
    show_create_modal = False

    if request.method == "POST" and request.POST.get("action") == "create_treino":
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
                show_create_modal = True
            else:
                treino.save()
                return redirect("prof_dashboard")
        else:
            show_create_modal = True

    now = timezone.localtime()
    upcoming_filter = Q(data__gt=now.date()) | (Q(data=now.date()) & Q(hora_fim__gte=now.time()))
    base_upcoming_qs = base_qs.filter(upcoming_filter)
    qs = base_upcoming_qs.order_by("data", "hora_inicio")

    selected_date = request.GET.get("data", "")
    raw_ct = request.GET.get("ct", "")
    selected_ct = None

    if selected_date:
        qs = qs.filter(data=selected_date)
    if raw_ct:
        try:
            selected_ct = int(raw_ct)
            qs = qs.filter(ct_id=selected_ct)
        except (TypeError, ValueError):
            selected_ct = None

    treinos = list(qs)
    for treino in treinos:
        confirmadas = getattr(treino, "confirmadas", 0) or 0
        treino.vagas_disponiveis = max(treino.vagas - confirmadas, 0)
    total_treinos = len(treinos)
    upcoming_qs = base_upcoming_qs
    next_treino_alunos = 0
    next_treino = None
    upcoming_for_stats = upcoming_qs
    if selected_date:
        upcoming_for_stats = upcoming_for_stats.filter(data=selected_date)
    if selected_ct:
        upcoming_qs = upcoming_qs.filter(ct_id=selected_ct)
        upcoming_for_stats = upcoming_for_stats.filter(ct_id=selected_ct)
    next_treino = upcoming_for_stats.order_by("data", "hora_inicio").first()
    if next_treino:
        next_treino_alunos = next_treino.inscricoes.filter(status=Inscricao.Status.CONFIRMADA).count()

    cts = request.user.cts_associados.order_by("nome")
    context = {
        "treinos": treinos,
        "cts": cts,
        "selected_date": selected_date,
        "selected_ct": selected_ct,
        "total_treinos": total_treinos,
        "next_treino": next_treino,
        "next_treino_alunos": next_treino_alunos,
        "treino_form": form,
        "show_create_modal": show_create_modal,
    }
    return render(request, "professor/dashboard.html", context)

@aluno_required
def meus_treinos(request):
    inscricoes = (
        Inscricao.objects
        .select_related("treino", "treino__ct")
        .filter(aluno=request.user)
        .order_by("treino__data", "treino__hora_inicio")
    )
    return render(request, "aluno/meus_treinos.html", {"inscricoes": inscricoes})


# --- Inscrições (Aluno) ---
@aluno_required
def inscricao_criar(request, treino_id: int):
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
            messages.success(request, "Inscrição reativada e confirmada!")
        else:
            messages.info(request, "Você já está inscrito neste treino.")
    else:
        if confirmadas >= treino.vagas:
            messages.error(request, "Treino lotado. Não foi possível realizar a inscrição.")
            return redirect("meus_treinos")
        Inscricao.objects.create(
            treino=treino, aluno=request.user, status=Inscricao.Status.CONFIRMADA
        )
        messages.success(request, "Inscrição realizada com sucesso!")
    return redirect("meus_treinos")


@aluno_required
def inscricao_cancelar(request, pk: int):
    if request.method != "POST":
        return redirect("meus_treinos")
    insc = get_object_or_404(Inscricao, pk=pk, aluno=request.user)
    if insc.status != Inscricao.Status.CANCELADA:
        insc.status = Inscricao.Status.CANCELADA
        insc.save(update_fields=["status"])
        messages.success(request, "Inscrição cancelada.")
    else:
        messages.info(request, "Inscrição já estava cancelada.")
    return redirect("meus_treinos")


@aluno_required
def novo_treino_escolher_ct(request):
    cts = CentroTreinamento.objects.all().order_by("nome")
    return render(request, "aluno/novo_treino_escolher_ct.html", {"cts": cts})


@aluno_required
def novo_treino_escolher_treino(request, ct_id: int):
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
    model = CentroTreinamento
    template_name = "ct/ct_confirm_delete.html"
    success_url = reverse_lazy("ct_list")

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
    if not hasattr(request.user, "usuario") or request.user.usuario.tipo != Usuario.Tipo.GERENTE:
        # Redireciona conforme perfil
        return redirect("home")
    cts = CentroTreinamento.objects.filter(gerente=request.user).order_by("nome")
    return render(request, "gerente/meus_cts.html", {"cts": cts})


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


class TreinoUpdateView(ProfessorRequiredMixin, UpdateView):
    model = Treino
    form_class = TreinoForm
    template_name = "professor/treino_form.html"
    success_url = reverse_lazy("prof_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return Treino.objects.filter(professor=self.request.user)

    def form_valid(self, form):
        data = form.cleaned_data.get("data")
        ct = form.cleaned_data.get("ct")
        hi = form.cleaned_data.get("hora_inicio")
        hf = form.cleaned_data.get("hora_fim")
        # Revalida associação professor-CT
        form.instance.full_clean(exclude=None)
        if data and ct and hi and hf:
            overlap = Treino.objects.filter(
                professor=self.request.user,
                ct=ct,
                data=data,
                hora_inicio__lt=hf,
                hora_fim__gt=hi,
            ).exclude(pk=self.object.pk).exists()
            if overlap:
                form.add_error(None, "Conflito de horário com outro treino seu neste CT.")
                return self.form_invalid(form)
        return super().form_valid(form)


class TreinoDeleteView(ProfessorRequiredMixin, DeleteView):
    model = Treino
    template_name = "professor/treino_confirm_delete.html"
    success_url = reverse_lazy("prof_dashboard")

    def get_queryset(self):
        return Treino.objects.filter(professor=self.request.user)


class TreinoDetailView(ProfessorRequiredMixin, DetailView):
    model = Treino
    template_name = "professor/treino_detail.html"

    def get_queryset(self):
        return Treino.objects.select_related("ct").filter(professor=self.request.user)


# --- Perfil (Aluno/Professor) ---
@login_required
def perfil_detail(request):
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
