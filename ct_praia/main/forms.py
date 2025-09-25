from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import CentroTreinamento, Treino, Usuario

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
    
class SignupGerenteForm(UserCreationForm):
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
        fields = ["nome", "endereco", "contato", "modalidades", "cnpj"]
        widgets = {
            "modalidades": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get("cnpj", "")
        # Normaliza para apenas dígitos
        digits = "".join(ch for ch in cnpj if ch.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError("CNPJ deve ter 14 dígitos.")
        # Mantemos armazenado com máscara padrão 00.000.000/0000-00
        masked = f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
        return masked


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


class UsuarioProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["telefone", "nivel", "certificacoes"]
        widgets = {
            "certificacoes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, usuario_tipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Guarda o tipo do usuário para lógica de exibição e limpeza
        self._usuario_tipo = usuario_tipo
        # Se não for professor, não exibe o campo certificações
        if usuario_tipo != Usuario.Tipo.PROFESSOR and "certificacoes" in self.fields:
            self.fields.pop("certificacoes")

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Se não for professor, garante que certificações fique vazio
        if getattr(self, "_usuario_tipo", None) != Usuario.Tipo.PROFESSOR:
            obj.certificacoes = ""
        if commit:
            obj.save()
        return obj

