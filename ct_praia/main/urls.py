from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/register/aluno/", views.signup_aluno, name="signup_aluno"),
    path("accounts/register/professor/", views.signup_professor, name="signup_professor"),
    path("accounts/register/gerente/", views.signup_gerente, name="signup_gerente"),
    path("aluno/meus-treinos/", views.meus_treinos, name="meus_treinos"),
    path("aluno/novo-treino/", views.novo_treino_escolher_ct, name="novo_treino_ct"),
    path("aluno/novo-treino/<int:ct_id>/", views.novo_treino_escolher_treino, name="novo_treino_escolher_treino"),
    path("professor/dashboard/", views.prof_dashboard, name="prof_dashboard"),
    # Gerente
    path("gerente/cts/", views.gerente_meus_cts, name="meus_cts"),
    path("gerente/cts/novo/", views.GerenteCTCreateView.as_view(), name="novo_ct"),
    path("gerente/cts/<int:pk>/professores/", views.gerente_ct_professores, name="gerente_ct_professores"),
    # Inscrições (Aluno)
    path("aluno/inscrever/<int:treino_id>/", views.inscricao_criar, name="inscricao_criar"),
    path("aluno/inscricao/<int:pk>/cancelar/", views.inscricao_cancelar, name="inscricao_cancelar"),
    path("ct/", views.CTListView.as_view(), name="ct_list"),
    path("ct/novo/", views.CTCreateView.as_view(), name="ct_create"),
    path("ct/<int:pk>/", views.CTDetailView.as_view(), name="ct_detail"),
    path("ct/<int:pk>/editar/", views.CTUpdateView.as_view(), name="ct_update"),
    path("ct/<int:pk>/excluir/", views.CTDeleteView.as_view(), name="ct_delete"),
    path("professor/treinos/novo/", views.TreinoCreateView.as_view(), name="treino_create"),
    # Perfil
    path("perfil/", views.perfil_detail, name="perfil_detail"),
    path("perfil/editar/", views.perfil_editar, name="perfil_editar"),
]
