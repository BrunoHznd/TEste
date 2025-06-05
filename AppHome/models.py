from django.db import models
from django.contrib.auth.models import User

class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cpf_cnh = models.CharField(max_length=18, unique=True)

    def __str__(self):
        return f"{self.user.username} - CPF/CNH: {self.cpf_cnh}"
