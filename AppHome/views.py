from urllib import request
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from pymongo import MongoClient
from django.http import JsonResponse
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from .forms import CadastroForm
from AppHome.models import Perfil
from .forms import CadastroForm
from django.contrib.auth import login


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    
    return render(request, 'login.html')

def cadastro_view(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CadastroForm()

    return render(request, 'cadastro.html', {'form': form})


def home_view(request):
    return render(request, 'home.html')


def faixa_horaria(hora):
    if 5 <= hora < 11:
        return "Manhã"
    elif 11 <= hora < 15:
        return "Almoço"
    elif 15 <= hora < 18:
        return "Tarde"
    else:
        return "Noite"


def dia_da_semana(numero):
    dias = {
        0: 'Segunda', 1: 'Terça', 2: 'Quarta',
        3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'
    }
    return dias.get(numero, 'Desconhecido')

from datetime import datetime, timedelta
from pymongo import MongoClient
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def tendencias_view(request):
    dia_param = request.GET.get("dia", "hoje")
    client = MongoClient("mongodb://localhost:27017")
    db = client["mototec"]
    pedidos = db["pedidos"]

    # Define data alvo (hoje, ontem, etc.)
    dias_ref = {
        "hoje": 0,
        "ontem": 1,
    }
    delta = dias_ref.get(dia_param, 0)
    data_alvo = (datetime.now() - timedelta(days=delta)).date()
    data_str = data_alvo.strftime("%Y-%m-%d")

    # Pipeline de agregação
    pipeline = [
        {"$match": {
            "data_hora": {"$regex": f"^{data_str}"},
            "bairro": {"$exists": True, "$ne": ""}
        }},
        {"$addFields": {
            "data_parse": {
                "$dateFromString": {
                    "dateString": "$data_hora",
                    "format": "%Y-%m-%d %H:%M:%S"
                }
            }
        }},
        {"$addFields": {
            "hora": {"$hour": "$data_parse"}
        }},
        {"$addFields": {
            "faixa": {
                "$switch": {
                    "branches": [
                        {"case": {"$and": [{"$gte": ["$hora", 5]}, {"$lt": ["$hora", 11]}]}, "then": "Manhã"},
                        {"case": {"$and": [{"$gte": ["$hora", 11]}, {"$lt": ["$hora", 15]}]}, "then": "Almoço"},
                        {"case": {"$and": [{"$gte": ["$hora", 15]}, {"$lt": ["$hora", 18]}]}, "then": "Tarde"},
                        {"case": {"$or": [{"$gte": ["$hora", 18]}, {"$lt": ["$hora", 5]}]}, "then": "Noite"}
                    ],
                    "default": "Outro"
                }
            }
        }},
        {"$group": {
            "_id": {
                "bairro": "$bairro",
                "faixa": "$faixa"
            },
            "total": {"$sum": 1}
        }},
        {"$sort": {"total": -1}}
    ]

    resultados = list(pedidos.aggregate(pipeline))

    # Encontrar o bairro com mais pedidos por faixa horária
    faixas = ["Manhã", "Almoço", "Tarde", "Noite"]
    agrupados = {faixa: {} for faixa in faixas}
    for doc in resultados:
        faixa = doc["_id"]["faixa"]
        bairro = doc["_id"]["bairro"]
        total = doc["total"]
        if faixa in faixas:
            agrupados[faixa][bairro] = total

    top_bairros = []
    for faixa in faixas:
        bairros = agrupados.get(faixa, {})
        if bairros:
            bairro_top = max(bairros.items(), key=lambda x: x[1])
            top_bairros.append({
                "bairro": bairro_top[0],
                "horario": faixa,
                "pedidos": bairro_top[1],
                "dia": data_alvo.strftime("%A")  # Nome do dia da semana
            })

    context = {
        "modo": "dia",
        "referencia": dia_param.capitalize(),
        "semana": top_bairros,
        "tendencias": [],
        "logs": []
    }
    return render(request, "tendencias.html", context)

@login_required
def restaurantes_view(request):
    """
    Busca os Top 3 restaurantes com mais pedidos nas últimas 24 horas
    e renderiza o template lista_restaurantes.html com contexto:
      restaurantes = [
        {
          "nome": "...",
          "bairro": "...",
          "latitude": -23.xxxxxx,
          "longitude": -46.xxxxxx,
          "pedidos_hoje": 123
        },
        ...
      ]
    Se não houver pedidos hoje em nenhum restaurante, passa lista vazia.
    """

    # 1) Conecta ao MongoDB (ajuste a URI se necessário)
    client = MongoClient("mongodb://localhost:27017")
    db = client["mototec"]
    pedidos_col = db["pedidos"]
    restaurantes_col = db["restaurantes"]

    # 2) Define o intervalo “hoje” (da meia-noite até a meia-noite seguinte)
    agora = datetime.now()
    hoje_str = agora.strftime("%Y-%m-%d")
    inicio_hoje = datetime.strptime(f"{hoje_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
    fim_hoje = inicio_hoje + timedelta(days=1)

    # 3) Pipeline de agregação para contar quantos pedidos cada restaurante teve hoje
    pipeline = [
        {
            # Converte data_hora (string) em Date para comparação
            "$addFields": {
                "data_parse": {
                    "$dateFromString": {
                        "dateString": "$data_hora",
                        "format": "%Y-%m-%d %H:%M:%S"
                    }
                }
            }
        },
        {
            # Filtra apenas pedidos cujo data_parse está entre início e fim de hoje
            "$match": {
                "data_parse": {"$gte": inicio_hoje, "$lt": fim_hoje},
                "restaurante_id": {"$exists": True}
            }
        },
        {
            # Agrupa por restaurante_id e conta a quantidade de pedidos
            "$group": {
                "_id": "$restaurante_id",
                "count": {"$sum": 1}
            }
        },
        {
            # Ordena em ordem decrescente pelo número de pedidos
            "$sort": {"count": -1}
        },
        {
            # Limita a 3 documentos (Top 3)
            "$limit": 3
        }
    ]

    top_ids = list(pedidos_col.aggregate(pipeline, allowDiskUse=True))
    # top_ids exemplo: [ {"_id": 234, "count": 377}, {"_id": 102, "count": 360}, {"_id": 192, "count": 355} ]

    restaurantes = []
    for doc in top_ids:
        rest_id = doc["_id"]
        count_pedidos = doc["count"]

        # Busca dados do restaurante pelo id
        resta = restaurantes_col.find_one({"id": rest_id})
        if not resta:
            continue

        restaurantes.append({
            "nome": resta.get("nome", "N/D"),
            "bairro": resta.get("bairro", "N/D"),
            "latitude": resta.get("latitude", 0.0),
            "longitude": resta.get("longitude", 0.0),
            "pedidos_hoje": count_pedidos
        })

    # Passa a lista (talvez vazia) ao template
    return render(request, "lista_restaurantes.html", {
        "restaurantes": restaurantes
    })

def mapa_view(request):
    return render(request, 'mapa.html')


def demanda_view(request):
    """
    Retorna JSON com pontos de calor (lat, lng, intensidade),
    filtrando pedidos das últimas 24 horas e agrupando por bin de 0.001° (~100 m).
    """
    if not request.user.is_authenticated:
        return JsonResponse({"dados": []})

    client = MongoClient("mongodb://localhost:27017")
    db = client["mototec"]
    pedidos = db["pedidos"]
    restaurantes_col = db["restaurantes"]

    agora = datetime.now()
    corte_24h = agora - timedelta(hours=24)

    pipeline_restaurantes_ativos = [
        {
            "$addFields": {
                "data_parse": {
                    "$dateFromString": {
                        "dateString": "$data_hora",
                        "format": "%Y-%m-%d %H:%M:%S"
                    }
                }
            }
        },
        {
            "$match": {
                "data_parse": {"$gte": corte_24h},
                "restaurante_id": {"$exists": True}
            }
        },
        {
            "$group": {
                "_id": "$restaurante_id"
            }
        }
    ]

    ativos_ids = list(pedidos.aggregate(pipeline_restaurantes_ativos, allowDiskUse=True))
    if not ativos_ids:
        return JsonResponse({"dados": []})

    coordenadas_arredondadas = []
    for doc in ativos_ids:
        rid = doc["_id"]
        resta = restaurantes_col.find_one({"id": rid})
        if not resta:
            continue
        lat = resta.get("latitude")
        lng = resta.get("longitude")
        if lat is None or lng is None:
            continue

        lat_arred = round(lat, 3)
        lng_arred = round(lng, 3)
        coordenadas_arredondadas.append((lat_arred, lng_arred))

    if not coordenadas_arredondadas:
        return JsonResponse({"dados": []})

    bins = {}
    for (lat_a, lng_a) in coordenadas_arredondadas:
        key = f"{lat_a}:{lng_a}"
        bins[key] = bins.get(key, 0) + 1

    max_contagem = max(bins.values())

    pontos_heat = []
    for key, contagem in bins.items():
        lat_str, lng_str = key.split(":")
        lat = float(lat_str)
        lng = float(lng_str)
        intensidade = contagem / max_contagem if max_contagem > 0 else 0.0
        pontos_heat.append([lat, lng, intensidade])
    return JsonResponse({"dados": pontos_heat})