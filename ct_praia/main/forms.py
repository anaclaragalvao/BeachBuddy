from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

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
