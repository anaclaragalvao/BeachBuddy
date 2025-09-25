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
    # Inscrições (Aluno)
    path("aluno/inscrever/<int:treino_id>/", views.inscricao_criar, name="inscricao_criar"),
    path("aluno/inscricao/<int:pk>/cancelar/", views.inscricao_cancelar, name="inscricao_cancelar"),
    path("ct/", views.CTListView.as_view(), name="ct_list"),
    path("ct/novo/", views.CTCreateView.as_view(), name="ct_create"),
    path("ct/<int:pk>/", views.CTDetailView.as_view(), name="ct_detail"),
    path("ct/<int:pk>/editar/", views.CTUpdateView.as_view(), name="ct_update"),
    path("ct/<int:pk>/excluir/", views.CTDeleteView.as_view(), name="ct_delete"),
    path("professor/treinos/", views.TreinoListView.as_view(), name="treino_list"),
    path("professor/treinos/novo/", views.TreinoCreateView.as_view(), name="treino_create"),
    path("professor/treinos/<int:pk>/", views.TreinoDetailView.as_view(), name="treino_detail"),
    path("professor/treinos/<int:pk>/editar/", views.TreinoUpdateView.as_view(), name="treino_update"),
    path("professor/treinos/<int:pk>/excluir/", views.TreinoDeleteView.as_view(), name="treino_delete"),
]
