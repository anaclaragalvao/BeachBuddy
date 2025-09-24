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
from .forms import CentroTreinamentoForm, TreinoForm
from .mixins import ProfOrManagerRequiredMixin, ProfessorRequiredMixin

from .forms import SignupAlunoForm, SignupProfessorForm
from .models import Usuario, Inscricao
from .decorators import aluno_required, professor_required

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


@professor_required
def prof_dashboard(request):
    # Dashboard mínimo: lista de treinos que o professor ministra
    treinos = (
        request.user.treinos_ministrados.select_related("ct").order_by("data", "hora_inicio")
        if request.user.is_authenticated else []
    )
    return render(request, "professor/dashboard.html", {"treinos": treinos})

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

class CTDetailView(DetailView):
    model = CentroTreinamento
    template_name = "ct/ct_detail.html"
    context_object_name = "ct"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        treinos = (
            self.object.treinos
            .select_related("ct", "professor")
            .annotate(confirmadas=Count("inscricoes", filter=Q(inscricoes__status=Inscricao.Status.CONFIRMADA)))
            .filter(data__gte=today)
            .order_by("data", "hora_inicio")
        )
        ctx["treinos"] = list(treinos)
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

class CTUpdateView(ProfOrManagerRequiredMixin, UpdateView):
    model = CentroTreinamento
    form_class = CentroTreinamentoForm
    template_name = "ct/ct_form.html"
    success_url = reverse_lazy("ct_list")

class CTDeleteView(ProfOrManagerRequiredMixin, DeleteView):
    model = CentroTreinamento
    template_name = "ct/ct_confirm_delete.html"
    success_url = reverse_lazy("ct_list")


# --- Treino CRUD (Professor) ---
class TreinoListView(ProfessorRequiredMixin, ListView):
    model = Treino
    template_name = "professor/treino_list.html"
    context_object_name = "treinos"

    def get_queryset(self):
        qs = Treino.objects.select_related("ct").filter(professor=self.request.user)
        data = self.request.GET.get("data")
        if data:
            qs = qs.filter(data=data)
        return qs.order_by("data", "hora_inicio")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["selected_date"] = self.request.GET.get("data", "")
        return ctx


class TreinoCreateView(ProfessorRequiredMixin, CreateView):
    model = Treino
    form_class = TreinoForm
    template_name = "professor/treino_form.html"
    success_url = reverse_lazy("treino_list")

    def form_valid(self, form):
        form.instance.professor = self.request.user
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
    success_url = reverse_lazy("treino_list")

    def get_queryset(self):
        return Treino.objects.filter(professor=self.request.user)

    def form_valid(self, form):
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
            ).exclude(pk=self.object.pk).exists()
            if overlap:
                form.add_error(None, "Conflito de horário com outro treino seu neste CT.")
                return self.form_invalid(form)
        return super().form_valid(form)


class TreinoDeleteView(ProfessorRequiredMixin, DeleteView):
    model = Treino
    template_name = "professor/treino_confirm_delete.html"
    success_url = reverse_lazy("treino_list")

    def get_queryset(self):
        return Treino.objects.filter(professor=self.request.user)


class TreinoDetailView(ProfessorRequiredMixin, DetailView):
    model = Treino
    template_name = "professor/treino_detail.html"

    def get_queryset(self):
        return Treino.objects.select_related("ct").filter(professor=self.request.user)
