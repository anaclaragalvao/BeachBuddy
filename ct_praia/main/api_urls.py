from django.urls import include, path
from rest_framework.routers import DefaultRouter


from . import api_views

# Router para ViewSets
router = DefaultRouter()
router.register(r'centros-treinamento', api_views.CentroTreinamentoViewSet, basename='ct')
router.register(r'treinos', api_views.TreinoViewSet, basename='treino')
router.register(r'inscricoes', api_views.InscricaoViewSet, basename='inscricao')
router.register(r'usuarios', api_views.UsuarioViewSet, basename='usuario')
router.register(r'agendamentos', api_views.AgendamentoTreinoViewSet, basename='agendamento')
router.register(r'professores-ct', api_views.ProfessorCentroTreinamentoViewSet, basename='professor_ct')

urlpatterns = [

    
    # Cadastro e login personalizado
    path('auth/signup/', api_views.signup_view, name='api_signup'),
    path('auth/login/', api_views.login_view, name='api_login'),
    
    # Métricas públicas
    path('metrics/', api_views.metrics_view, name='api_metrics'),
    
    # Rotas dos ViewSets
    path('', include(router.urls)),
]
