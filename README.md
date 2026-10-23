# Sistema de Microsserviços para Logística Urbana

Sistema de três microsserviços que se comunicam via HTTP para medir prazo, custo e desempenho de entregas de uma transportadora urbana (dados sintéticos). Atividade para Nota 2.

## Visão geral

| Serviço | Porta | Função |
|---|---|---|
| `servico-dados` | 8001 | Armazena motoristas, veículos e entregas no PostgreSQL; expõe endpoints de leitura/escrita |
| `servico-processamento` | 8002 | Consome o Serviço de Dados via HTTP e calcula indicadores (pontualidade, atrasos, custo/km, ranking, outliers) |
| `servico-relatorio` | 8003 | Orquestra Dados e Processamento e gera o relatório final em JSON, CSV ou HTML |
| `db` (PostgreSQL 16.10) | 5432 (apenas rede interna) | Banco relacional, sem porta publicada no host |

```
 Cliente / Navegador
        |  HTTP :8003
        v
 +------------------+   GET /metricas/completo   +-----------------------+
 | servico-relatorio| -------------------------> | servico-processamento |
 +------------------+                            +-----------------------+
        |  GET /resumo                                      |  GET /entregas, /motoristas
        v                                                   v
 +------------------------------------------------------------+
 |                      servico-dados :8001                    |
 +------------------------------------------------------------+
                              |  SQL (rede logistica-net)
                              v
                       +--------------+
                       |  db (Postgres)|
                       +--------------+
```

## Pré-requisitos

- Docker e Docker Compose v2.1+ (necessário para a opção `--wait`)
- (Opcional, para os testes) Python 3.12

## Como executar

```bash
docker compose up -d --build --wait
docker compose ps
```

Na primeira subida o Serviço de Dados cria o esquema e carrega 20 motoristas, 12 veículos e 400 entregas (semente fixa `42`, sempre os mesmos números). Reiniciar os contêineres não duplica os dados.

Para sobrescrever senha e portas, copie `.env.example` para `.env`. A senha do banco não tem valor padrão no código do `servico-dados`; o `docker-compose.yml` fornece o padrão didático.

Encerrar: `docker compose down`. Zerar também o banco: `docker compose down -v`.

## Exemplos de uso

No PowerShell use `curl.exe` (e não o alias `curl`) ou `Invoke-RestMethod`.

```bash
curl http://localhost:8001/resumo
curl "http://localhost:8001/entregas?regiao=Centro&limit=5"
curl http://localhost:8002/metricas/completo
curl "http://localhost:8003/relatorio?formato=json"
curl -o relatorio.csv "http://localhost:8003/relatorio?formato=csv"
```

Para ver o relatório HTML, abra `http://localhost:8003/relatorio?formato=html` no navegador.

Criar um veículo:

```bash
curl -X POST http://localhost:8001/veiculos -H "Content-Type: application/json" \
  -d '{"placa":"XYZ1A23","tipo":"VAN","capacidade_kg":1200,"ano":2024}'
```

## Endpoints

### Serviço de Dados (8001)

| Método | Caminho | Descrição |
|---|---|---|
| GET | `/health` | Saúde do serviço e do banco |
| GET | `/resumo` | Contagem de motoristas, veículos e entregas |
| GET | `/motoristas` | Lista paginada; filtro `cidade_base` |
| GET | `/motoristas/<id>` | Detalhe (404 se não existir) |
| POST | `/motoristas` | Cria motorista (`nome`, `cnh_categoria`, `cidade_base`, `data_admissao`) |
| GET | `/veiculos` | Lista paginada; filtro `tipo` |
| GET | `/veiculos/<id>` | Detalhe |
| POST | `/veiculos` | Cria veículo; placa duplicada retorna 409 |
| GET | `/entregas` | Lista paginada; filtros `regiao`, `status`, `motorista_id`, `veiculo_id`, `data_inicio`, `data_fim` |
| GET | `/entregas/<id>` | Detalhe |
| POST | `/entregas` | Cria entrega (valida chaves estrangeiras, enums e datas; `peso_kg` deve ser > 0) |
| PATCH | `/entregas/<id>` | Atualiza `status`, `entregue_em` e/ou `custo` |

Paginação: `limit` (padrão 100, máximo 1000) e `offset`. Resposta: `{"total", "limit", "offset", "itens": [...]}`. Erros: JSON `{"erro": "..."}` com status 400 (entrada inválida), 404 (recurso inexistente), 405 (método não permitido), 409 (placa duplicada), 500 (erro interno) ou 503 (banco indisponível).

Data/hora: os timestamps são armazenados sem fuso horário (naive). Se a requisição trouxer deslocamento (`Z`, `-03:00`), o deslocamento é descartado e o horário informado é mantido como está; envie sempre o horário local sem deslocamento.

### Serviço de Processamento (8002)

Todos aceitam os filtros opcionais `regiao`, `data_inicio` e `data_fim`.

| Método | Caminho | Descrição |
|---|---|---|
| GET | `/health` | Saúde do serviço |
| GET | `/metricas/resumo` | Indicadores gerais (% no prazo, atraso médio, custo/km...) |
| GET | `/metricas/status` | Entregas por status |
| GET | `/metricas/regioes` | Desempenho por região |
| GET | `/metricas/motoristas/ranking` | Ranking (`top`, `min_entregas`) |
| GET | `/metricas/atrasos-criticos` | Atrasos acima de `limite_min` (padrão 120) |
| GET | `/metricas/outliers-custo` | Outliers de custo/km pela regra do IQR |
| GET | `/metricas/completo` | Todos os blocos acima em uma única resposta |

Erros: 400 se um parâmetro for inválido (`top`, `min_entregas`, `limite_min`) ou se o Serviço de Dados rejeitar os filtros; 502 se o Serviço de Dados estiver indisponível.

### Serviço de Relatório (8003)

| Método | Caminho | Descrição |
|---|---|---|
| GET | `/health` | Saúde do serviço |
| GET | `/` | Índice com os formatos disponíveis |
| GET | `/relatorio?formato=json\|csv\|html` | Relatório consolidado (padrão `json`; outro valor retorna 400). Aceita `regiao`, `data_inicio`, `data_fim` |

Erros: 400 se `formato` for inválido ou se os filtros forem rejeitados pelos serviços dependentes; 502, com o campo `"servico"` (`"dados"` ou `"processamento"`), se algum serviço dependente estiver fora do ar, lento ou responder algo inválido.

## Timeouts e retentativas

Regra: cada camada espera mais do que a camada abaixo leva no pior caso. Processamento→Dados: `HTTP_TIMEOUT=5` s com 2 tentativas (≈ 11 s por chamada); Relatório→Processamento: `HTTP_TIMEOUT=30` s; gunicorn `--timeout 60` s no Processamento e no Relatório (maior que o `HTTP_TIMEOUT` do Relatório). Assim a falha é reportada pelo serviço mais próximo da causa em vez de estourar o timeout do chamador.

## Regra de atraso

O atraso não é armazenado, é derivado: para entregas `ENTREGUE`, `atraso_min = max(0, entregue_em - prazo_previsto)` em minutos. "No prazo" significa `atraso_min == 0`. Atraso crítico: 120 minutos ou mais.

## Testes

Pré-requisito: Python 3.12. Opcionalmente crie um ambiente virtual (`python -m venv .venv` e `.venv\Scripts\Activate.ps1` no PowerShell, ou `source .venv/bin/activate` no Linux/macOS). Depois, na raiz do projeto:

```bash
pip install -r requirements-dev.txt
python rodar_testes.py
```

O script roda o pytest uma vez por serviço (cada serviço tem seu `pytest.ini`), sem Docker, rede ou banco: as chamadas HTTP e o acesso ao PostgreSQL são simulados. As dependências de teste ficam nos `requirements-dev.txt` e não entram nas imagens. Cobertura: cálculos, cliente HTTP, rotas dos três serviços, validação do Serviço de Dados, CSV do relatório e o gerador de dados.

## Limitações

- Sem autenticação, sem HTTPS: todos os endpoints (inclusive POST/PATCH) são abertos. Uso didático apenas.
- Dados sintéticos; senha padrão do banco presente no `docker-compose.yml` apenas para fins didáticos.
- Sem fila, cache ou escalonamento: a comunicação é síncrona, então a queda de um serviço afeta os que dependem dele.
- Dependências transitivas: Werkzeug e Jinja2 estão fixadas, mas itsdangerous, click, blinker e MarkupSafe não têm lockfile; as imagens base estão fixadas por versão de patch (`python:3.12.12-slim`, `postgres:16.10-alpine`), não por digest. `pip-audit` não foi executado.
- Duplicação deliberada: pequenas utilidades (leitura do filtro `regiao`/`data_inicio`/`data_fim`, conversão de parâmetros inteiros, handler de erros HTTP) aparecem repetidas em mais de um serviço de propósito, para manter os serviços independentes (sem biblioteca compartilhada e sem acoplamento de build).

## Entregáveis
Arquivos da atividade na pasta `docs/` (gerados a partir das evidências reais em `docs/evidencias/`):
- `docs/Relatorio_Atividade_Nota2.docx`: relatório (Capa, Introdução, Metodologia, Resultados, Conclusão, Referências).
- `docs/Apresentacao_Atividade_Nota2.pptx`: apresentação de 12 slides, com notas do orador (cerca de 8 minutos).
- `docs/diagrama_arquitetura.png` e `docs/grafico_*.png`: figuras usadas nos dois documentos.
- Para regerar (com a pasta `docs/evidencias/` presente): `python docs/gerar_diagrama.py`, `python docs/gerar_graficos.py`, `python docs/gerar_relatorio.py` e `python docs/gerar_apresentacao.py`. Requer `python-docx`, `python-pptx`, `matplotlib` e `pillow`.
