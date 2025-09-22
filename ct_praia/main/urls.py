from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/register/aluno/", views.signup_aluno, name="signup_aluno"),
    path("accounts/register/professor/", views.signup_professor, name="signup_professor"),
    path("aluno/meus-treinos/", views.meus_treinos, name="meus_treinos"),
    path("professor/dashboard/", views.prof_dashboard, name="prof_dashboard"),
]
