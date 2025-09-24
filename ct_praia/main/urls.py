from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/register/aluno/", views.signup_aluno, name="signup_aluno"),
    path("accounts/register/professor/", views.signup_professor, name="signup_professor"),
    path("aluno/meus-treinos/", views.meus_treinos, name="meus_treinos"),
    path("professor/dashboard/", views.prof_dashboard, name="prof_dashboard"),
    path("ct/", views.CTListView.as_view(), name="ct_list"),
    path("ct/novo/", views.CTCreateView.as_view(), name="ct_create"),
    path("ct/<int:pk>/", views.CTDetailView.as_view(), name="ct_detail"),
    path("ct/<int:pk>/editar/", views.CTUpdateView.as_view(), name="ct_update"),
    path("ct/<int:pk>/excluir/", views.CTDeleteView.as_view(), name="ct_delete"),
    # Treinos (Professor)
    path("professor/treinos/", views.TreinoListView.as_view(), name="treino_list"),
    path("professor/treinos/novo/", views.TreinoCreateView.as_view(), name="treino_create"),
    path("professor/treinos/<int:pk>/", views.TreinoDetailView.as_view(), name="treino_detail"),
    path("professor/treinos/<int:pk>/editar/", views.TreinoUpdateView.as_view(), name="treino_update"),
    path("professor/treinos/<int:pk>/excluir/", views.TreinoDeleteView.as_view(), name="treino_delete"),
]
