"""ct_praia URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from main import views
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetCompleteView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Configuração do Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="BeachBuddy API",
        default_version='v1',
        description="API REST para o sistema BeachBuddy - Plataforma de gerenciamento de treinos de beach tennis",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="galvaopclara@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API REST
    path('api/', include('main.api_urls')),
    
    # Swagger/OpenAPI Documentation
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # URLs originais do Django (templates)
    path("", include("main.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/register/", views.signup_aluno, name="signup"),
    path('seguranca/password_reset/', PasswordResetView.as_view(
        template_name='seguranca/password_reset_form.html',
        success_url=reverse_lazy('sec-password_reset_done'),
        html_email_template_name='seguranca/password_reset_email.html',
        subject_template_name='seguranca/password_reset_subject.txt',
        from_email='galvaopclara@gmail.com',
    ), name='password_reset'),
    path('seguranca/password_reset_done/', PasswordResetDoneView.as_view(
        template_name='seguranca/password_reset_done.html',
    ), name='sec-password_reset_done'),
    path('seguranca/password_reset_confirm/<uidb64>/<token>/',
         PasswordResetConfirmView.as_view(
             template_name='seguranca/password_reset_confirm.html',
             success_url=reverse_lazy('sec-password_reset_complete'),
         ), name='password_reset_confirm'),
    path('seguranca/password_reset_complete/', PasswordResetCompleteView.as_view(
        template_name='seguranca/password_reset_complete.html'
    ), name='sec-password_reset_complete'),

]
