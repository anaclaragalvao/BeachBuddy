from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

'''Views relacionadas à autenticação e páginas básicas.
class PainelView(LoginRequiredMixin, TemplateView):
    template_name = "painel.html"
    login_url = "/accounts/login/"
'''

def home(request):
    return render(request, "base.html")

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cadastro criado com sucesso! Faça login.")
            return redirect("login")  # nome da rota de login do Django
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})

'''
@login_required
def painel_privado(request):
    return render(request, "painel.html")
    '''