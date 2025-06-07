from urllib import request
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from .forms import SenhaRecuperadaForm
from pymongo import MongoClient
from django.http import JsonResponse
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from .forms import CadastroForm
from AppHome.models import Perfil
from .forms import CadastroForm
from django.contrib.auth import login


def splash_view(request):
    return render(request, 'splash.html')


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


def haversine(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em metros entre dois pontos geográficos
    usando a fórmula de Haversine.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Raio da Terra em metros
    R = 6371000
    
    # Converte graus para radianos
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Diferenças das coordenadas
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Fórmula de Haversine
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distancia = R * c
    
    return distancia

def demanda_teste(request):
    """
    Endpoint de teste para o heatmap com dados estáticos.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Não autenticado"}, status=401)
    
    # Dados de exemplo para teste
    pontos_teste = [
        {
            "lat": -24.0167,
            "lng": -46.4667,
            "intensidade": 0.8,
            "total_pedidos": 15,
            "quantidade_restaurantes": 3,
            "restaurantes": [
                {"id": 1, "nome": "Restaurante Teste 1", "pedidos": 8},
                {"id": 2, "nome": "Restaurante Teste 2", "pedidos": 5},
                {"id": 3, "nome": "Restaurante Teste 3", "pedidos": 2}
            ]
        },
        {
            "lat": -24.0267,
            "lng": -46.4767,
            "intensidade": 0.5,
            "total_pedidos": 8,
            "quantidade_restaurantes": 2,
            "restaurantes": [
                {"id": 4, "nome": "Restaurante Teste 4", "pedidos": 5},
                {"id": 5, "nome": "Restaurante Teste 5", "pedidos": 3}
            ]
        },
        {
            "lat": -24.0067,
            "lng": -46.4567,
            "intensidade": 0.3,
            "total_pedidos": 4,
            "quantidade_restaurantes": 1,
            "restaurantes": [
                {"id": 6, "nome": "Restaurante Teste 6", "pedidos": 4}
            ]
        }
    ]
    
    return JsonResponse({"status": "ok", "data": pontos_teste})

class SenhaRecuperadaForm(PasswordResetView):
    template_name = 'recuperacao.html'
    form_class = SenhaRecuperadaForm
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'

def demanda_view(request):
    """
    Retorna JSON com pontos de calor agrupando restaurantes próximos
    em um raio de 500m, com intensidade baseada no número de pedidos.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Não autenticado"}, status=401)

    try:
        # Conecta ao MongoDB
        client = MongoClient("mongodb://localhost:27017")
        db = client["mototec"]
        pedidos = db["pedidos"]
        restaurantes_col = db["restaurantes"]
        
        # Verifica se as coleções existem
        if "pedidos" not in db.list_collection_names() or "restaurantes" not in db.list_collection_names():
            return JsonResponse({
                "status": "ok", 
                "data": [],
                "message": "Coleções 'pedidos' ou 'restaurantes' não encontradas no banco de dados"
            })

        # 1. Busca pedidos das últimas 24 horas
        agora = datetime.now()
        corte_24h = agora - timedelta(hours=24)
        data_corte_str = corte_24h.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"[DEBUG] Buscando pedidos a partir de: {data_corte_str}")
        
        # 2. Busca restaurantes com pedidos recentes e suas coordenadas
        try:
            pipeline = [
                {
                    "$match": {
                        "data_hora": {"$gte": data_corte_str},
                        "restaurante_id": {"$exists": True}
                    }
                },
                {
                    "$group": {
                        "_id": "$restaurante_id",
                        "total_pedidos": {"$sum": 1},
                        "bairro": {"$first": "$bairro"}
                    }
                }
            ]
            
            print("[DEBUG] Executando pipeline de agregação...")
            pedidos_por_restaurante = list(pedidos.aggregate(pipeline, allowDiskUse=True))
            print(f"[DEBUG] Encontrados {len(pedidos_por_restaurante)} restaurantes com pedidos recentes")
            
            if not pedidos_por_restaurante:
                print("[DEBUG] Nenhum pedido encontrado nas últimas 24 horas")
                return JsonResponse({"status": "ok", "data": []})
                
        except Exception as e:
            print(f"[ERRO] Erro ao executar agregação: {str(e)}")
            return JsonResponse({"status": "error", "message": f"Erro ao processar dados: {str(e)}"}, status=500)
        
        # 3. Busca as coordenadas dos restaurantes
        restaurantes_info = {}
        restaurantes_sem_coordenadas = 0
        
        print("[DEBUG] Buscando coordenadas dos restaurantes...")
        
        for pedido in pedidos_por_restaurante:
            restaurante_id = pedido["_id"]
            try:
                # Tenta converter o ID para inteiro se necessário
                try:
                    restaurante_id_int = int(restaurante_id)
                    restaurante = restaurantes_col.find_one({"$or": [
                        {"id": restaurante_id},
                        {"id": restaurante_id_int}
                    ]})
                except (ValueError, TypeError):
                    restaurante = restaurantes_col.find_one({"id": restaurante_id})
                
                if not restaurante:
                    print(f"[AVISO] Restaurante não encontrado: {restaurante_id}")
                    continue
                    
                if "latitude" not in restaurante or "longitude" not in restaurante:
                    restaurantes_sem_coordenadas += 1
                    continue
                
                # Garante que as coordenadas são números
                try:
                    lat = float(restaurante["latitude"])
                    lng = float(restaurante["longitude"])
                    
                    restaurantes_info[str(restaurante_id)] = {
                        "lat": lat,
                        "lng": lng,
                        "nome": restaurante.get("nome", f"Restaurante {restaurante_id}"),
                        "bairro": pedido.get("bairro", ""),
                        "pedidos": pedido["total_pedidos"]
                    }
                except (ValueError, TypeError) as e:
                    print(f"[ERRO] Coordenadas inválidas para restaurante {restaurante_id}: {e}")
                    
            except Exception as e:
                print(f"[ERRO] Erro ao processar restaurante {restaurante_id}: {str(e)}")
        
        print(f"[DEBUG] Restaurantes com coordenadas: {len(restaurantes_info)}")
        print(f"[DEBUG] Restaurantes sem coordenadas: {restaurantes_sem_coordenadas}")
        
        if not restaurantes_info:
            print("[AVISO] Nenhum restaurante com coordenadas válidas encontrado")
            return JsonResponse({"status": "ok", "data": []})
        
        if not restaurantes_info:
            return JsonResponse({"status": "ok", "data": []})
        
        # 4. Agrupa restaurantes próximos (dentro de 500m)
        grupos = []
        processados = set()
        
        print(f"[DEBUG] Iniciando agrupamento de {len(restaurantes_info)} restaurantes...")
        
        for restaurante_id, info in list(restaurantes_info.items()):
            if restaurante_id in processados:
                continue
                
            print(f"[DEBUG] Criando novo grupo para restaurante {restaurante_id}")
                
            # Cria um novo grupo
            grupo = {
                "ids": [restaurante_id],
                "lats": [info["lat"]],
                "lngs": [info["lng"]],
                "total_pedidos": info["pedidos"],
                "restaurantes": [
                    {
                        "id": restaurante_id,
                        "nome": info["nome"],
                        "pedidos": info["pedidos"]
                    }
                ]
            }
            
            # Verifica restaurantes próximos
            for other_id, other_info in restaurantes_info.items():
                if (other_id in processados or 
                    other_id == restaurante_id or 
                    other_id in grupo["ids"]):
                    continue
                    
                # Calcula distância entre os restaurantes
                try:
                    distancia = haversine(
                        info["lat"], info["lng"],
                        other_info["lat"], other_info["lng"]
                    )
                    
                    # Se estiver a menos de 500m, adiciona ao grupo
                    if distancia <= 500:  # 500 metros
                        print(f"[DEBUG] Adicionando restaurante {other_id} ao grupo (distância: {distancia:.2f}m)")
                        grupo["ids"].append(other_id)
                        grupo["lats"].append(other_info["lat"])
                        grupo["lngs"].append(other_info["lng"])
                        grupo["total_pedidos"] += other_info["pedidos"]
                        grupo["restaurantes"].append({
                            "id": other_id,
                            "nome": other_info["nome"],
                            "pedidos": other_info["pedidos"]
                        })
                except Exception as e:
                    print(f"[ERRO] Erro ao calcular distância entre {restaurante_id} e {other_id}: {str(e)}")
            
            # Calcula o centro do grupo
            try:
                grupo["lat"] = sum(grupo["lats"]) / len(grupo["lats"])
                grupo["lng"] = sum(grupo["lngs"]) / len(grupo["lngs"])
                
                print(f"[DEBUG] Grupo formado com {len(grupo['ids'])} restaurantes, centro em ({grupo['lat']}, {grupo['lng']})")
                
                # Adiciona os IDs ao conjunto de processados
                for rid in grupo["ids"]:
                    processados.add(rid)
                
                grupos.append(grupo)
                
            except Exception as e:
                print(f"[ERRO] Erro ao calcular centro do grupo: {str(e)}")
        
        print(f"[DEBUG] Total de grupos formados: {len(grupos)}")
        
        # 5. Prepara os dados para o heatmap
        if not grupos:
            print("[AVISO] Nenhum grupo formado para o heatmap")
            return JsonResponse({"status": "ok", "data": []})
        
        try:
            # Encontra o máximo de pedidos para normalização
            max_pedidos = max(grupo["total_pedidos"] for grupo in grupos)
            print(f"[DEBUG] Máximo de pedidos em um grupo: {max_pedidos}")
            
            # Prepara os pontos de calor
            pontos_calor = []
            for i, grupo in enumerate(grupos):
                try:
                    # Normaliza a intensidade (0 a 1)
                    intensidade = (grupo["total_pedidos"] / max_pedidos) if max_pedidos > 0 else 0.5
                    
                    # Limita a intensidade entre 0.1 e 1.0 para melhor visualização
                    intensidade = max(0.1, min(1.0, intensidade))
                    
                    # Ordena os restaurantes por número de pedidos (maior primeiro)
                    restaurantes_ordenados = sorted(
                        grupo["restaurantes"], 
                        key=lambda x: x["pedidos"], 
                        reverse=True
                    )
                    
                    # Limita a 5 restaurantes no popup
                    if len(restaurantes_ordenados) > 5:
                        restaurantes_popup = restaurantes_ordenados[:5]
                        mais_restaurantes = len(restaurantes_ordenados) - 5
                    else:
                        restaurantes_popup = restaurantes_ordenados
                        mais_restaurantes = 0
                    
                    # Formata os dados do ponto de calor
                    ponto = {
                        "lat": float(grupo["lat"]),
                        "lng": float(grupo["lng"]),
                        "intensidade": float(intensidade),
                        "total_pedidos": int(grupo["total_pedidos"]),
                        "quantidade_restaurantes": len(grupo["restaurantes"]),
                        "restaurantes": restaurantes_popup,
                        "mais_restaurantes": mais_restaurantes
                    }
                    
                    pontos_calor.append(ponto)
                    
                    print(f"[DEBUG] Ponto {i+1}: {ponto['quantidade_restaurantes']} restaurantes, "
                          f"{ponto['total_pedidos']} pedidos, intensidade: {ponto['intensidade']:.2f}")
                    
                except Exception as e:
                    print(f"[ERRO] Erro ao processar grupo {i}: {str(e)}")
            
            print(f"[DEBUG] Total de pontos de calor gerados: {len(pontos_calor)}")
            
        except Exception as e:
            print(f"[ERRO CRÍTICO] Erro ao gerar pontos de calor: {str(e)}")
            return JsonResponse({
                "status": "error", 
                "message": f"Erro ao processar pontos de calor: {str(e)}"
            }, status=500)
        
        # 6. Retorna os dados
        try:
            print(f"[DEBUG] Retornando {len(pontos_calor)} pontos de calor")
            return JsonResponse({
                "status": "ok",
                "data": pontos_calor
            })
            
        except Exception as e:
            print(f"[ERRO CRÍTICO] Erro ao serializar resposta: {str(e)}")
            return JsonResponse({
                "status": "error", 
                "message": "Erro ao preparar resposta"
            }, status=500)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)