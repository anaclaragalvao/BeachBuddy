from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import CentroTreinamento, Treino

User = get_user_model()

class SignupAlunoForm(UserCreationForm):
    first_name = forms.CharField(label="Nome", max_length=30, required=False)
    email = forms.EmailField(label="E-mail", required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado.")
        return email


class SignupProfessorForm(UserCreationForm):
    first_name = forms.CharField(label="Nome", max_length=30, required=False)
    email = forms.EmailField(label="E-mail", required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado.")
        return email
    


class CentroTreinamentoForm(forms.ModelForm):
    class Meta:
        model = CentroTreinamento
        fields = ["nome", "endereco", "contato", "modalidades"]
        widgets = {
            "modalidades": forms.Textarea(attrs={"rows": 4}),
        }


class TreinoForm(forms.ModelForm):
    class Meta:
        model = Treino
        # professor será definido pela view; não expor no form
        fields = [
            "ct",
            "modalidade",
            "data",
            "hora_inicio",
            "hora_fim",
            "vagas",
            "nivel",
            "observacoes",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

