from django import forms
from .models import Perfil
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

def __init__(self, *args, **kwargs):
    super(CadastroForm, self).__init__(*args, **kwargs)
    for field in self.fields.values():
        field.widget.attrs.update({
            'class': 'mt-1 block w-full px-4 py-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500',
        })
    

class CadastroForm(UserCreationForm):
    email = forms.EmailField(required=True)
    cpf_cnh = forms.CharField(max_length=18, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        # O campo CPF/CNH será salvo depois em um perfil ou model à parte
        if commit:
            user.save()
            Perfil.objects.create(user=user, cpf_cnh=self.cleaned_data['cpf_cnh']) 
        return user
