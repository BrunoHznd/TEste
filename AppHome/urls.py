from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from .views import SenhaRecuperadaForm,CustomPasswordResetDoneView,CustomPasswordResetConfirmView,CustomPasswordResetCompleteView

urlpatterns = [
    path('', views.splash_view, name='splash'),
    path('principal/', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('tendencias/', views.tendencias_view, name='tendencias'),
    path('restaurantes/', views.restaurantes_view, name='lista_restaurantes'),
    path('mapa/', views.mapa_view, name='mapa'),
    path('api/demanda/', views.demanda_view, name='demanda'),
    
    # URLs para recuperação de senha
    path('recuperar-senha/', 
         SenhaRecuperadaForm.as_view(), 
         name='password_reset'),
    path('recuperar-senha/enviado/', 
         CustomPasswordResetDoneView.as_view(), 
         name='password_reset_done'),
    path('recuperar-senha/<uidb64>/<token>/', 
         CustomPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('recuperar-senha/concluido/', 
         CustomPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),
]
