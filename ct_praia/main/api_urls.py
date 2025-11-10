from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import api_views

# Router para ViewSets
router = DefaultRouter()
router.register(r'centros-treinamento', api_views.CentroTreinamentoViewSet, basename='ct')
router.register(r'treinos', api_views.TreinoViewSet, basename='treino')
router.register(r'inscricoes', api_views.InscricaoViewSet, basename='inscricao')
router.register(r'usuarios', api_views.UsuarioViewSet, basename='usuario')

urlpatterns = [
    # Autenticação JWT
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Cadastro e login personalizado
    path('auth/signup/', api_views.signup_view, name='api_signup'),
    path('auth/login/', api_views.login_view, name='api_login'),
    
    # Métricas públicas
    path('metrics/', api_views.metrics_view, name='api_metrics'),
    
    # Rotas dos ViewSets
    path('', include(router.urls)),
]
