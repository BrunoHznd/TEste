from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from datetime import datetime, timedelta
from collections import Counter

app = FastAPI()

# 🔗 Conexão com MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["mototec"]
pedidos = db["pedidos"]

# 🔥 Configuração dos templates HTML
templates = Jinja2Templates(directory="AppHome/templates")


# ✔️ Função para conversão de dia da semana
def dia_da_semana(numero):
    dias = {
        0: 'Segunda',
        1: 'Terça',
        2: 'Quarta',
        3: 'Quinta',
        4: 'Sexta',
        5: 'Sábado',
        6: 'Domingo'
    }
    return dias.get(numero, 'Desconhecido')


# ✔️ Função para converter string em datetime
def converter_data(data_str):
    try:
        return datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"[ERRO] Conversão de data falhou para '{data_str}': {e}")
        return None


# ✔️ Função para gerar análise
def gerar_analise(data_minima=None):
    dados = list(pedidos.find({}))
    contador = Counter()

    for doc in dados:
        data_obj = converter_data(doc.get("data_hora"))

        if not data_obj:
            continue

        if data_minima and data_obj < data_minima:
            continue

        bairro = doc.get("bairro", "Desconhecido")
        dia_semana = data_obj.weekday()  # 0 = segunda, 6 = domingo
        hora = data_obj.hour

        # 🔥 Definindo faixa horária
        if 5 <= hora < 11:
            faixa = "Manhã"
        elif 11 <= hora < 15:
            faixa = "Almoço"
        elif 15 <= hora < 18:
            faixa = "Tarde"
        else:
            faixa = "Noite"

        chave = (bairro, dia_semana, faixa)
        contador[chave] += 1

    resultados = []
    for chave, total in contador.items():
        resultados.append({
            "bairro": chave[0],
            "dia": dia_da_semana(chave[1]),
            "horario": chave[2],
            "total": total
        })

    return resultados


# ✔️ Página HTML de tendências
@app.get("/tendencias", response_class=HTMLResponse)
def tendencias(request: Request):
    print("\n====================")
    print("[LOG] 🚀 Gerando tendências...")

    hoje = datetime.now()
    sete_dias_atras = hoje - timedelta(days=7)

    # 🔍 Tendências da Semana
    print("[LOG] 🔍 Processando dados da semana...")
    semana = gerar_analise(sete_dias_atras)

    # 🔍 Tendência Geral (todo histórico)
    print("[LOG] 🔍 Processando dados gerais...")
    tendencias_geral = gerar_analise()

    print("[LOG] ✅ Processamento concluído.")
    print("====================\n")

    return templates.TemplateResponse(
        "tendencias.html",
        {
            "request": request,
            "semana": semana,
            "tendencias": tendencias_geral
        }
    )