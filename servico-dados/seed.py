"""Gerador deterministico de dados sinteticos (random.Random(42), data base fixa)."""
import random
from datetime import datetime, timedelta

SEMENTE = 42
DATA_BASE = datetime(2026, 3, 1)
DIAS_PERIODO = 92  # 2026-03-01 ... 2026-05-31
TOTAL_ENTREGAS = 400

NOMES = [
    "Carlos Eduardo Souza", "Marcos Vinícius Lima", "João Pedro Alves",
    "Rafael Henrique Costa", "Anderson Luiz Pereira", "Fernando Augusto Ramos",
    "Ricardo Almeida Santos", "Paulo Roberto Mendes", "Lucas Gabriel Ferreira",
    "Thiago Martins Rocha", "Bruno César Barbosa", "Diego Fernandes Nunes",
    "Gustavo Henrique Dias", "Rodrigo Teixeira Cardoso", "Felipe Augusto Moreira",
    "Eduardo Batista Araújo", "Marcelo Antunes Ribeiro", "André Luís Carvalho",
    "Sérgio Ricardo Lopes", "Leandro Gomes Monteiro",
]

# (multiplicador de distancia, fator de propensao a atraso) por regiao
REGIOES = {
    "Centro": (0.6, 0.7),
    "Zona Sul": (0.9, 0.9),
    "Zona Oeste": (1.0, 1.0),
    "Zona Norte": (1.15, 1.25),
    "Zona Leste": (1.25, 1.4),
}

CIDADES_BASE = ["Sé", "Santana", "Santo Amaro", "Tatuapé", "Lapa"]

# tipo: (quantidade, capacidade_kg, faixa de distancia km, custo por km, faixa de peso kg)
TIPOS = {
    "MOTO": (3, 30, (2, 25), 1.8, (1, 20)),
    "VAN": (4, 1200, (5, 45), 2.8, (20, 400)),
    "CAMINHAO_LEVE": (3, 3500, (8, 55), 3.6, (100, 1500)),
    "CAMINHAO": (2, 12000, (15, 60), 5.2, (500, 8000)),
}


def _gerar_placa(rng, usadas):
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    while True:
        placa = (
            "".join(rng.choice(letras) for _ in range(3))
            + str(rng.randint(0, 9))
            + rng.choice(letras)
            + f"{rng.randint(0, 99):02d}"
        )
        if placa not in usadas:
            usadas.add(placa)
            return placa


def gerar_dados():
    """Retorna dict com listas de tuplas prontas para insercao.

    As entregas referenciam motoristas/veiculos por indice (base 0); o
    chamador converte para os ids reais gerados pelo banco.
    """
    rng = random.Random(SEMENTE)

    # Motoristas
    motoristas = []
    propensao = []
    for nome in NOMES:
        cnh = rng.choice(["B", "C", "C", "D", "E"])
        cidade = rng.choice(CIDADES_BASE)
        admissao = (DATA_BASE - timedelta(days=rng.randint(180, 3000))).date()
        motoristas.append((nome, cnh, cidade, admissao))
        propensao.append(round(rng.uniform(0.05, 0.45), 3))

    # Veiculos
    veiculos = []
    tipos_veiculo = []
    placas = set()
    for tipo, (qtd, capacidade, _, _, _) in TIPOS.items():
        for _ in range(qtd):
            veiculos.append((_gerar_placa(rng, placas), tipo, capacidade, rng.randint(2015, 2025)))
            tipos_veiculo.append(tipo)

    nomes_regioes = list(REGIOES)
    entregas = []
    for _ in range(TOTAL_ENTREGAS):
        m = rng.randrange(len(motoristas))
        v = rng.randrange(len(veiculos))
        regiao = rng.choice(nomes_regioes)
        mult_dist, fator_atraso = REGIOES[regiao]
        _, _, (dmin, dmax), custo_km, (pmin, pmax) = TIPOS[tipos_veiculo[v]]

        distancia = round(min(60.0, max(2.0, rng.uniform(dmin, dmax) * mult_dist)), 2)
        custo = round(distancia * custo_km * rng.uniform(0.9, 1.15) * (1 + (mult_dist - 1) * 0.3), 2)
        peso = round(rng.uniform(pmin, pmax), 2)

        saida = DATA_BASE + timedelta(
            days=rng.randrange(DIAS_PERIODO),
            hours=7 + rng.randrange(12),
            minutes=rng.randrange(60),
        )
        prazo = saida + timedelta(minutes=int(round(30 + distancia * 2.5)))

        sorteio = rng.random()
        if sorteio < 0.85:
            status = "ENTREGUE"
        elif sorteio < 0.91:
            status = "EM_ROTA"
        elif sorteio < 0.96:
            status = "CANCELADA"
        else:
            status = "FALHA"

        entregue_em = None
        if status == "ENTREGUE":
            if rng.random() < 0.03:
                delta = rng.randint(130, 300)  # atraso critico
            elif rng.random() < min(0.9, propensao[m] * fator_atraso):
                delta = rng.randint(5, 90)  # atraso comum
            else:
                delta = -rng.randint(0, 25)  # no prazo (ou adiantada)
            entregue_em = prazo + timedelta(minutes=delta)

        entregas.append([m, v, regiao, status, distancia, custo, peso, saida, prazo, entregue_em])

    # Ids cronologicos
    entregas.sort(key=lambda e: e[7])

    # 3 outliers de custo (x3) entre entregas concluidas de veiculos maiores
    candidatas = [
        i for i, e in enumerate(entregas)
        if e[3] == "ENTREGUE" and tipos_veiculo[e[1]] != "MOTO"
    ]
    for i in rng.sample(candidatas, 3):
        entregas[i][5] = round(entregas[i][5] * 3, 2)

    return {
        "motoristas": motoristas,
        "veiculos": veiculos,
        "entregas": [tuple(e) for e in entregas],
    }
