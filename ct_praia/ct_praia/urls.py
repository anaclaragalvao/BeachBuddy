"""ct_praia URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from main import views
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetCompleteView

urlpatterns = [
    path('admin/', admin.site.urls),
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
