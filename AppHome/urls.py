from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('home/', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('tendencias/', views.tendencias_view, name='tendencias'),
    path('restaurantes/', views.restaurantes_view, name='lista_restaurantes'),
    path('mapa/', views.mapa_view, name='mapa'),
    path('api/demanda/', views.demanda_view, name='demanda'),
]
