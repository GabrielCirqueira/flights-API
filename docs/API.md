# Especificação da API REST — voobarato-flights-api

Microsserviço HTTP (FastAPI) que conecta o Voo Barato (Symfony, apps) ao Google Flights via biblioteca `fli`.

| Item | Valor |
|---|---|
| Base URL (local) | `http://127.0.0.1:12000` |
| Formato | JSON UTF-8 |
| Idioma dos campos | Português (PT-BR) |
| Swagger interativo | `http://127.0.0.1:12000/docs` |

---

## Índice

1. [Convenções gerais](#convenções-gerais)
2. [Busca aberta — como ler a resposta](#busca-aberta--como-ler-a-resposta)
3. [Campos opcionais e padrões](#campos-opcionais-e-padrões)
4. [Erros e códigos HTTP](#erros-e-códigos-http)
5. [Enums aceitos](#enums-aceitos)
6. [Modelos de resposta compartilhados](#modelos-de-resposta-compartilhados)
7. [Endpoints](#endpoints)
   - [GET /saude](#get-saude)
   - [POST /api/v1/buscar](#post-apiv1buscar)
   - [POST /api/v1/buscar/janela](#post-apiv1buscarjanela)
   - [POST /api/v1/buscar/aberta](#post-apiv1buscaraberta)
   - [POST /api/v1/buscar/por-local](#post-apiv1buscarpor-local)
   - [GET /api/v1/aeroportos](#get-apiv1aeroportos)
   - [GET /api/v1/aeroportos/{codigo_iata}](#get-apiv1aeroportoscodigo_iata)
   - [GET /api/v1/cidades](#get-apiv1cidades)
8. [Exemplos de integração](#exemplos-de-integração)

---

## Convenções gerais

### Cabeçalhos

| Cabeçalho | Obrigatório | Rotas | Descrição |
|---|---|---|---|
| `Content-Type: application/json` | Sim (POST) | Todas POST | Corpo sempre JSON |
| `X-Internal-Token` | Condicional | `/api/v1/*` | Obrigatório **somente se** `FLIGHTS_API_INTERNAL_TOKEN` estiver definido no servidor |
| `X-Request-ID` | Não | Todas | ID de correlação enviado pelo cliente; se omitido, a API gera um UUID |
| `X-Correlation-ID` | Não | Todas | Alias aceito no lugar de `X-Request-ID` |

Toda resposta inclui `X-Request-ID` no cabeçalho HTTP (gerado ou repassado).

### CORS

Origens permitidas vêm de **`CORS_ORIGINS`** (URLs extras, vírgula) **+ localhost de dev** (sempre ativos).

| Origem | Quando |
|---|---|
| `localhost:8010`, `localhost:3000` | Sempre (dev local) |
| URLs em `CORS_ORIGINS` | Adicionadas em prod/staging |

```bash
CORS_ORIGINS=https://seu-dominio.exemplo.com
```

### Autenticação

```http
X-Internal-Token: voobarato_secret_token_12345
```

| Cenário | Comportamento |
|---|---|
| Token configurado no servidor + header ausente/errado | `401` → `{"error": "nao_autorizado"}` |
| Token **não** configurado no servidor (dev local) | Rotas `/api/v1/*` ficam abertas |
| Rota `/saude` | Sempre pública, ignora token |

### Qual endpoint usar?

| Objetivo | Endpoint |
|---|---|
| Health check / Docker | `GET /saude` |
| Mostrar preço ao usuário em **data exata** | `POST /api/v1/buscar` |
| Alerta **sem data** — explorar próximos N dias (cidade/estado) | `POST /api/v1/buscar/aberta` |
| Busca por local com **data fixa** ou sem data (mesmo comportamento) | `POST /api/v1/buscar/por-local` |
| Heatmap por IATA em intervalo ou sem datas | `POST /api/v1/buscar/janela` |
| Autocomplete de aeroportos | `GET /api/v1/aeroportos` |
| Autocomplete exclusivo de cidades/estados | `GET /api/v1/cidades` ou `GET /api/v1/cities` |

### Configuração — busca sem data

| Variável de ambiente | Padrão | Descrição |
|---|---|---|
| `OPEN_SEARCH_WINDOW_DAYS` | `90` | Dias escaneados quando nenhuma data é informada (hoje → hoje+N) |

A janela **se desloca automaticamente** a cada requisição — não é um mês fixo. Ideal para alertas recorrentes via cron.

---

## Busca aberta — como ler a resposta

Endpoints afetados: **`POST /api/v1/buscar/aberta`** e **`POST /api/v1/buscar/por-local`** (sem `data_partida`).

A resposta tem **duas camadas**. Não confunda resumo com voo completo.

### Camada 1 — `por_data[]` (calendário)

Lista **uma entrada por dia** dentro da janela, com o **menor preço** daquele dia (melhor par IATA entre origem × destino).

| Campo | O que é | Serve para |
|---|---|---|
| `data` | Dia ISO (`2026-09-01`) | Mostrar no calendário / WhatsApp |
| `preco` | Menor preço do dia | Comparar datas rapidamente |
| `moeda` | Ex: `BRL` | Exibição |
| `aeroporto_origem_iata` | IATA origem do par vencedor | Saber qual aeroporto saiu mais barato |
| `aeroporto_destino_iata` | IATA destino do par vencedor | Idem destino |
| `oferta` | **Objeto completo do voo** ou `null` | Detalhes, link, trechos, cidades |

> **`por_data` sozinho (sem `oferta`)** = só calendário de preços. Isso acontece quando `expandir_top: 0`.

### Camada 2 — `oferta` dentro de `por_data[]` e lista `ofertas[]`

Quando a API **expande** uma data, busca o voo real naquele dia e preenche `oferta` com o mesmo JSON da busca por data fixa:

- `trechos[]` — horários, aeroportos, número do voo
- `rota_iata[]` — rota com **IATA + nome da cidade**
- `aeroportos_conexao[]` — hubs de escala
- `url_busca_google_flights` — link direto pro Google Flights
- `direto`, `com_conexao`, `escalas`, `companhia_principal`, etc.

`ofertas[]` é a **mesma informação em lista plana** — um item por data expandida, ordenado por preço.  
`melhor_oferta` = atalho para o item mais barato de `ofertas[]`.

```
por_data[0].oferta  ≈  ofertas[0]   (mesmo schema OfertaBuscaPorLocalSaida)
```

### Parâmetro `expandir_top` — o que controla

| Valor enviado | Comportamento | `por_data[].oferta` | `ofertas[]` |
|---|---|---|---|
| **omitido** (`null`) | Expande **todas** as datas da janela | Preenchido em cada dia | Todas as ofertas |
| `0` | Só calendário, **sem** buscar voos | sempre `null` | `[]` |
| `5` | Expande só as **5 datas mais baratas** | preenchido nos 5 primeiros; resto `null` | 5 ofertas |
| `30` | Expande as 30 datas mais baratas | idem | até 30 ofertas |

> Janela de 90 dias com `expandir_top` omitido = até **90 consultas** ao Google Flights (mais lento). Para cron rápido, use `expandir_top: 10` ou `0` + notificação só com preço/data.

### Qual campo usar no Symfony / WhatsApp?

| Necessidade | Campo |
|---|---|
| Listar datas e preços no alerta | `por_data[].data` + `por_data[].preco` |
| Link, horário, companhia, rota com cidades | `por_data[].oferta` ou `ofertas[]` |
| Melhor opção geral | `melhor_oferta` |
| Milhas | Calcular no Symfony sobre `oferta.preco` |

### Exemplo visual da estrutura

```json
{
  "modo_busca": "aberta",
  "data_inicio": "2026-08-02",
  "data_fim": "2026-11-01",
  "janela_dias": 90,
  "por_data": [
    {
      "data": "2026-09-01",
      "preco": 400.0,
      "moeda": "BRL",
      "aeroporto_origem_iata": "VIX",
      "aeroporto_destino_iata": "CWB",
      "oferta": {
        "preco": 400.0,
        "moeda": "BRL",
        "direto": false,
        "com_conexao": true,
        "rota_iata": [
          { "iata": "VIX", "cidade": "Vitória" },
          { "iata": "GRU", "cidade": "São Paulo" },
          { "iata": "CWB", "cidade": "Curitiba" }
        ],
        "aeroportos_conexao": [{ "iata": "GRU", "cidade": "São Paulo" }],
        "url_busca_google_flights": "https://www.google.com/travel/flights?q=...",
        "trechos": [{ "iata_partida": "VIX", "data_hora_partida": "2026-09-01T18:40:00", "...": "..." }],
        "aeroporto_origem_iata": "VIX",
        "aeroporto_destino_iata": "CWB"
      }
    },
    {
      "data": "2026-09-02",
      "preco": 420.0,
      "moeda": "BRL",
      "aeroporto_origem_iata": "VIX",
      "aeroporto_destino_iata": "CWB",
      "oferta": null
    }
  ],
  "ofertas": [ "...mesma oferta de por_data[0].oferta..." ],
  "total": 1,
  "melhor_oferta": { "...": "..." }
}
```

No exemplo acima, `por_data[1].oferta` é `null` porque só a data `2026-09-01` foi expandida (`expandir_top: 1`). Com `expandir_top` omitido, **todas** teriam `oferta` preenchida.

---

## Campos opcionais e padrões

Regra geral para todos os POST:

| Situação | O que acontece |
|---|---|
| Campo **obrigatório** omitido | `422` — FastAPI retorna `detail[]` com `"Field required"` |
| Campo **opcional** omitido | Valor padrão do schema é aplicado automaticamente |
| Campo opcional enviado como `null` | Aceito quando o tipo permite (`data_retorno`, etc.) |
| IATA com minúsculas (`"vix"`) | Normalizado para maiúsculas (`"VIX"`) |
| Enum desconhecido (`maximo_escalas: "DIRECT"`) | Ignorado silenciosamente — cai no fallback `"ANY"` |
| Data inválida (`"10/08/2026"`) | `422` — formato deve ser `YYYY-MM-DD` |
| `expandir_top` omitido em `/aberta` ou `/por-local` | Expande **todas** as datas — `por_data[].oferta` + `ofertas[]` completos |
| `expandir_top: 0` em `/aberta` ou `/por-local` | Só calendário — `por_data` sem voo, `ofertas: []` |
| `data_partida` omitida em `/por-local` | Modo **aberto** — escaneia próximos N dias |
| `data_inicio`/`data_fim` omitidas em `/janela` | Modo aberto por **IATA** — hoje → hoje+N |
| `data_retorno` sem `data_partida` em `/por-local` | `422` — retorno exige ida |

---

## Erros e códigos HTTP

A API usa **dois formatos** de erro:

### 1. Validação Pydantic — HTTP `422`

Campos malformados, tipos errados, regras de negócio do schema (ex: data de retorno anterior à ida).

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "data_partida"],
      "msg": "Field required",
      "input": { "origem": "VIX", "destino": "GRU" }
    }
  ]
}
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, data_retorno não pode ser anterior a data_partida",
      "input": { "origem": "VIX", "destino": "GRU", "data_partida": "2026-08-10", "data_retorno": "2026-08-05" }
    }
  ]
}
```

### 2. Erro de aplicação — HTTP `4xx` / `502`

```json
{ "error": "mensagem descritiva em português" }
```

| HTTP | `error` típico | Quando |
|---|---|---|
| `401` | `nao_autorizado` | Token inválido ou ausente |
| `404` | `Aeroporto com código IATA 'ZZZ' não encontrado.` | IATA inexistente em `/aeroportos/{iata}` |
| `422` | `Código IATA desconhecido para o fli: ZZZ` | IATA não reconhecido pelo Google Flights na busca |
| `422` | `Não foi possível encontrar aeroportos para a origem '...'` | Cidade/estado sem aeroporto resolvível em `/por-local` |
| `502` | `upstream_search_failed` | Falha na comunicação com Google Flights |

### Busca sem resultados

Não é erro. Retorna `200` com `total: 0` e `ofertas: []`.

Exemplo — rota sem voo direto com `maximo_escalas: "NON_STOP"`:

```json
{
  "origem": "VIX",
  "destino": "GYN",
  "data_partida": "2026-08-10",
  "data_retorno": null,
  "moeda": "BRL",
  "ofertas": [],
  "total": 0
}
```

---

## Enums aceitos

### `classe_cabine` (padrão: `"ECONOMY"`)

| Valor | Significado |
|---|---|
| `ECONOMY` | Econômica |
| `PREMIUM_ECONOMY` | Econômica premium |
| `BUSINESS` | Executiva |
| `FIRST` | Primeira classe |

### `maximo_escalas` (padrão: `"ANY"`)

| Valor | Significado | Se omitir |
|---|---|---|
| `ANY` | Qualquer número de escalas | **(padrão)** — inclui conexões |
| `NON_STOP` | Só voos diretos | Rotas sem voo direto → lista vazia |
| `ONE_STOP` | Máximo 1 escala | — |
| `TWO_PLUS_STOPS` | Máximo 2 escalas | — |

### `ordenar_por` (padrão: `"CHEAPEST"`)

| Valor | Significado |
|---|---|
| `CHEAPEST` | Menor preço |
| `BEST` | Melhor custo-benefício |
| `TOP_FLIGHTS` | Voos mais populares |
| `DURATION` | Menor duração |
| `DEPARTURE_TIME` | Horário de partida |
| `ARRIVAL_TIME` | Horário de chegada |

### `origem_tipo` / `destino_tipo` (padrão: `"cidade"`)

| Valor | `*_valor` esperado | Exemplo |
|---|---|---|
| `cidade` | Nome da cidade (match exato, ignora acentos) | `"Vitória"`, `"São Paulo"` |
| `estado` | Sigla UF ou nome por extenso | `"ES"`, `"Goiás"` |
| `aeroporto` | Código IATA de 3 letras | `"GRU"`, `"VIX"` |

---

## Modelos de resposta compartilhados

### `OfertaVooSaida`

Presente em `/buscar`, `/buscar/janela` (`mais_baratas_expandidas`), `/buscar/por-local` e `/buscar/aberta` (`ofertas[]` e `por_data[].oferta`).

| Campo | Tipo | Descrição |
|---|---|---|
| `preco` | `float` | Preço total (só ida **ou** ida+volta, conforme a busca) |
| `moeda` | `string` | Ex: `"BRL"` |
| `duracao_minutos` | `int` | Duração total |
| `escalas` | `int` | Número de escalas |
| `direto` | `bool` | `true` = sem escalas |
| `com_conexao` | `bool` | `true` = passa por hub(s) |
| `rota_iata` | `array` | `[{ "iata": "VIX", "cidade": "Vitória" }, ...]` |
| `aeroportos_conexao` | `array` | Hubs intermediários (mesmo formato) |
| `companhia_principal` | `string` | Companhia principal |
| `nome_companhia_principal` | `string\|null` | Nome comercial |
| `trechos` | `array` | Pernas do voo (ver abaixo) |
| `url_busca_google_flights` | `string` | Link Google Flights (`one way` ou `returning`) |
| `encontrado_em` | `datetime` | UTC — momento da consulta |
| `fonte` | `string` | Sempre `"fli"` |

#### `trechos[]`

| Campo | Tipo | Descrição |
|---|---|---|
| `iata_partida` / `iata_chegada` | `string` | Código IATA |
| `aeroporto_partida` / `aeroporto_chegada` | `string` | Nome completo do aeroporto |
| `data_hora_partida` / `data_hora_chegada` | `datetime` | **Horário local do aeroporto** (sem `Z`/timezone) |
| `companhia_aerea` | `string` | Companhia do trecho |
| `numero_voo` | `string\|null` | Número do voo |
| `duracao_minutos` | `int\|null` | Duração do trecho |
| `aeronave` | `string\|null` | Modelo |
| `companhia_operadora` | `string\|null` | Operadora (codeshare) |

> **Preço só ida vs ida e volta:** com `data_retorno: null`, o preço é **apenas da ida**. No Google Flights, o mesmo trecho pode custar ~metade de um pacote ida e volta. Compare sempre o mesmo tipo de viagem.

> **Horários:** `"2026-08-10T18:40:00"` = 18h40 no fuso local do aeroporto, não UTC.

---

## Endpoints

---

### GET /saude

Health check. **Rota pública** — não exige token.

#### Requisição

Sem corpo. Sem parâmetros.

```bash
curl http://127.0.0.1:12000/saude
```

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `status` | `string` | Sempre `"ok"` |
| `servico` | `string` | Nome do serviço |
| `versao` | `string` | Versão da API |

```json
{
  "status": "ok",
  "servico": "voobarato-flights-api",
  "versao": "1.0.0"
}
```

---

### POST /api/v1/buscar

Busca pontual em **data exata**. Use para exibir preço ao usuário ou validar alerta em tempo real.

#### Requisição mínima (só ida)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: voobarato_secret_token_12345" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_partida": "2026-08-10"
  }'
```

**Campos enviados:** 3 obrigatórios.  
**Comportamento:** busca só ida, 1 adulto, econômica, qualquer escala, ordenado por preço, até 10 ofertas.

#### Requisição completa (ida e volta)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: voobarato_secret_token_12345" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_partida": "2026-08-10",
    "data_retorno": "2026-08-14",
    "adultos": 2,
    "criancas": 1,
    "classe_cabine": "ECONOMY",
    "maximo_escalas": "NON_STOP",
    "ordenar_por": "CHEAPEST",
    "limite_top": 5
  }'
```

#### Só voos diretos

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_partida": "2026-08-10",
    "maximo_escalas": "NON_STOP"
  }'
```

#### Campos da requisição

| Campo | Tipo | Obrig. | Padrão | Se omitir | Se inválido |
|---|---|---|---|---|---|
| `origem` | `string` | **Sim** | — | `422` Field required | IATA ≠ 3 letras → `422`; IATA desconhecido → `422` upstream |
| `destino` | `string` | **Sim** | — | `422` Field required | Idem origem |
| `data_partida` | `string` | **Sim** | — | `422` Field required | Formato ≠ `YYYY-MM-DD` → `422` |
| `data_retorno` | `string` | Não | `null` (só ida) | Busca só ida; preço de ida | Anterior a `data_partida` → `422` |
| `adultos` | `int` | Não | `1` | 1 adulto | `< 1` ou `> 9` → `422` |
| `criancas` | `int` | Não | `0` | Sem crianças | `< 0` ou `> 8` → `422` |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | Valor desconhecido → tratado como `ECONOMY` |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | `"NON_STOP"` em rota sem direto → `ofertas: []` |
| `ordenar_por` | `string` | Não | `"CHEAPEST"` | Ordena por preço | Valor desconhecido → `CHEAPEST` |
| `limite_top` | `int` | Não | `10` | Até 10 ofertas | `< 1` ou `> 50` → `422` |

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `origem` | `string` | IATA origem (normalizado) |
| `destino` | `string` | IATA destino |
| `data_partida` | `string` | Data ISO |
| `data_retorno` | `string\|null` | `null` se só ida |
| `moeda` | `string` | Moeda configurada (ex: `BRL`) |
| `ofertas` | `array` | Lista de `OfertaVooSaida`, ordenada por preço |
| `total` | `int` | Quantidade de ofertas |

```json
{
  "origem": "VIX",
  "destino": "GRU",
  "data_partida": "2026-08-10",
  "data_retorno": null,
  "moeda": "BRL",
  "total": 2,
  "ofertas": [
    {
      "preco": 452.0,
      "moeda": "BRL",
      "duracao_minutos": 100,
      "escalas": 0,
      "direto": true,
      "com_conexao": false,
      "rota_iata": [
        { "iata": "VIX", "cidade": "Vitória" },
        { "iata": "GRU", "cidade": "São Paulo" }
      ],
      "aeroportos_conexao": [],
      "companhia_principal": "Gol Transportes Aéreos",
      "nome_companhia_principal": "Gol",
      "trechos": [
        {
          "iata_partida": "VIX",
          "iata_chegada": "GRU",
          "aeroporto_partida": "Eurico de Aguiar Salles Airport",
          "aeroporto_chegada": "Guarulhos - Governador Andre Franco Montoro International Airport",
          "companhia_aerea": "Gol Transportes Aéreos",
          "numero_voo": "1387",
          "data_hora_partida": "2026-08-10T18:40:00",
          "data_hora_chegada": "2026-08-10T20:20:00",
          "duracao_minutos": 100,
          "aeronave": "Boeing 737",
          "companhia_operadora": null
        }
      ],
      "url_busca_google_flights": "https://www.google.com/travel/flights?q=Flights+from+VIX+to+GRU+on+2026-08-10+one+way&hl=pt-BR&gl=BR&curr=BRL",
      "encontrado_em": "2026-08-01T01:00:00.000000Z",
      "fonte": "fli"
    },
    {
      "preco": 372.0,
      "escalas": 1,
      "direto": false,
      "com_conexao": true,
      "rota_iata": [
        { "iata": "VIX", "cidade": "Vitória" },
        { "iata": "SSA", "cidade": "Salvador" },
        { "iata": "GRU", "cidade": "São Paulo" }
      ],
      "aeroportos_conexao": [{ "iata": "SSA", "cidade": "Salvador" }],
      "trechos": ["..."]
    }
  ]
}
```

> Voos **diretos e com conexão** podem coexistir na mesma rota. A lista vem por preço — o mais barato pode ser conexão mesmo existindo voo direto.

---

### POST /api/v1/buscar/janela

Preço **mínimo por dia** em um intervalo. Ideal para alertas e calendário de preços.

Também aceita **modo aberto** (sem datas) por IATA — use `/buscar/aberta` se a origem/destino forem **cidade/estado**.

**Não use** para exibir "preço agora" ao usuário sem expandir a data vencedora via `/buscar`.

#### Requisição com intervalo explícito

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_inicio": "2026-08-02",
    "data_fim": "2026-08-08"
  }'
```

**Resposta:** `modo_busca: "janela"`.

#### Requisição sem data (modo aberto)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "expandir_top": 0
  }'
```

**Se omitir `data_inicio` e `data_fim`:** escaneia hoje → hoje + `OPEN_SEARCH_WINDOW_DAYS` (padrão 90).  
**Resposta:** `modo_busca: "aberta"`, `janela_dias` preenchido.

#### Janela customizada (sem datas fixas)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "janela_dias": 30,
    "expandir_top": 3
  }'
```

**Se omitir datas mas enviar `janela_dias`:** escaneia hoje → hoje + 30 dias.

#### Sem expansão (só calendário de preços)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_inicio": "2026-08-02",
    "data_fim": "2026-08-08",
    "expandir_top": 0
  }'
```

**Se `expandir_top: 0`:** `mais_baratas_expandidas` retorna `[]`. Só vem `por_data`.

#### Expandir as 3 datas mais baratas

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_inicio": "2026-08-02",
    "data_fim": "2026-08-08",
    "expandir_top": 3
  }'
```

#### Campos da requisição

| Campo | Tipo | Obrig. | Padrão | Se omitir | Se inválido |
|---|---|---|---|---|---|
| `origem` | `string` | **Sim** | — | `422` | IATA inválido → `422` |
| `destino` | `string` | **Sim** | — | `422` | IATA inválido → `422` |
| `data_inicio` | `string` | Não | `null` | Modo aberto (hoje) | Formato inválido → `422` |
| `data_fim` | `string` | Não | `null` | Modo aberto (hoje+N) | Anterior a `data_inicio` → `422` |
| `janela_dias` | `int` | Não | `null` | Usa `OPEN_SEARCH_WINDOW_DAYS` (90) | 1–180; fora → `422` |
| `adultos` | `int` | Não | `1` | 1 adulto | Fora de 1–9 → `422` |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | — |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | — |
| `expandir_top` | `int` | Não | `1` | Expande 1 data | `0` = sem expansão; max `10` |

> Janela **não suporta** `data_retorno` — sempre busca só ida por dia.  
> Se informar só `data_inicio` (sem `data_fim`): intervalo = `data_inicio` → `data_inicio + janela_dias`.

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `origem` / `destino` | `string` | IATAs |
| `data_inicio` / `data_fim` | `string` | Intervalo efetivo (calculado se omitido) |
| `moeda` | `string` | Moeda |
| `modo_busca` | `string` | `"janela"` (datas informadas) ou `"aberta"` (sem datas) |
| `janela_dias` | `int\|null` | Preenchido no modo aberto |
| `por_data` | `array` | `{ data, preco, moeda }` por dia, ordenado por preço |
| `mais_baratas_expandidas` | `array` | `OfertaVooSaida` das N datas mais baratas |

```json
{
  "origem": "VIX",
  "destino": "GRU",
  "data_inicio": "2026-08-02",
  "data_fim": "2026-08-09",
  "moeda": "BRL",
  "modo_busca": "aberta",
  "janela_dias": 7,
  "por_data": [
    { "data": "2026-08-09", "preco": 452.0, "moeda": "BRL" },
    { "data": "2026-08-06", "preco": 846.0, "moeda": "BRL" }
  ],
  "mais_baratas_expandidas": []
}
```

---

### POST /api/v1/buscar/aberta

Atalho para **busca sem data por cidade, estado ou aeroporto** — mesmo contrato de entrada que `/buscar/por-local`, mas **sem** `data_partida`.

Equivalente a chamar `/buscar/por-local` omitindo a data. Retorna `RespostaBuscaPorLocal` com `modo_busca: "aberta"`.

Use para **alertas recorrentes** em que o usuário configurou rota por nome de cidade, sem data de ida nem volta.

#### Requisição mínima

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/aberta \
  -H "Content-Type: application/json" \
  -d '{
    "origem_valor": "Vitória",
    "destino_valor": "Goiânia"
  }'
```

**Comportamento:** resolve aeroportos, escaneia 90 dias (padrão), expande **todas** as datas com oferta completa (`expandir_top` omitido).

> Ver [Busca aberta — como ler a resposta](#busca-aberta--como-ler-a-resposta) para entender `por_data` vs `oferta` vs `ofertas[]`.

#### Só calendário (rápido, sem detalhes do voo)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/aberta \
  -H "Content-Type: application/json" \
  -d '{
    "origem_valor": "Vitória",
    "destino_valor": "Curitiba",
    "janela_dias": 30,
    "expandir_top": 0
  }'
```

Retorna `por_data[]` com data/preço/IATA — **`oferta: null`** em todos, **`ofertas: []`**.

#### Por estado

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/aberta \
  -H "Content-Type: application/json" \
  -d '{
    "origem_tipo": "estado",
    "origem_valor": "Espírito Santo",
    "destino_tipo": "estado",
    "destino_valor": "GO",
    "janela_dias": 60,
    "expandir_top": 0
  }'
```

#### Campos da requisição

| Campo | Tipo | Obrig. | Padrão | Se omitir | Se inválido |
|---|---|---|---|---|---|
| `origem_tipo` | `string` | Não | `"cidade"` | Assume cidade | Enum inválido → `422` |
| `origem_valor` | `string` | **Sim** | — | `422` | Cidade/estado sem aeroporto → `422` |
| `destino_tipo` | `string` | Não | `"cidade"` | Assume cidade | — |
| `destino_valor` | `string` | **Sim** | — | `422` | Sem aeroporto → `422` |
| `janela_dias` | `int` | Não | `90` (env) | Usa `OPEN_SEARCH_WINDOW_DAYS` | 1–180 |
| `adultos` | `int` | Não | `1` | 1 adulto | 1–9 |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | — |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | — |
| `expandir_top` | `int\|null` | Não | `null` (todas) | Expande **todas** as datas | `0` = só resumo; `N` = top N; max `180` |

Valores de `origem_tipo` / `destino_tipo`: `"cidade"`, `"estado"`, `"aeroporto"` (IATA em `*_valor`).

#### Resposta `200`

Mesmo formato de [POST /api/v1/buscar/por-local](#post-apiv1buscarpor-local) no modo aberto (`modo_busca: "aberta"`).

| Onde está o quê | Campo |
|---|---|
| Calendário dia a dia | `por_data[]` |
| Voo completo (link, trechos, cidades) | `por_data[].oferta` ou `ofertas[]` |
| Melhor preço geral | `melhor_oferta` |

Documentação detalhada: [Busca aberta — como ler a resposta](#busca-aberta--como-ler-a-resposta).

---

### POST /api/v1/buscar/por-local

Busca por **cidade, estado ou aeroporto** — o usuário não precisa saber IATA.

Suporta dois modos via `modo_busca` na resposta:

| Modo | Quando | O que retorna |
|---|---|---|
| `data_fixa` | `data_partida` informada | `ofertas[]` com todos os voos na data — **sem** `por_data` |
| `aberta` | `data_partida` omitida/`null` | `por_data[]` (calendário) + `por_data[].oferta` (voo completo) + `ofertas[]` |

#### Fluxo interno — modo `data_fixa`

1. Resolve origem e destino em até **3 aeroportos principais** cada
2. Gera combinações (ex: Vitória × São Paulo → VIX→GRU, VIX→CGH)
3. Busca em **paralelo** (até 4 threads)
4. **Cache** de 5 min por par IATA+data
5. Retorna **todas as ofertas** de todas as combinações, ordenadas por preço

#### Fluxo interno — modo `aberta`

1. Resolve aeroportos (igual acima)
2. Para cada par IATA, consulta preço mínimo por dia na janela (hoje → hoje+N)
3. Consolida `por_data[]` — por data, fica o par mais barato
4. Expande cada data (`expandir_top`) com **oferta completa** em `por_data[].oferta` e `ofertas[]`

#### Requisição mínima (cidade → cidade, data fixa)

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/por-local \
  -H "Content-Type: application/json" \
  -d '{
    "origem_tipo": "cidade",
    "origem_valor": "Vitória",
    "destino_tipo": "cidade",
    "destino_valor": "Goiânia",
    "data_partida": "2026-08-10"
  }'
```

#### Alerta sem data (modo aberto) — principal caso de uso

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/por-local \
  -H "Content-Type: application/json" \
  -d '{
    "origem_valor": "Vitória",
    "destino_valor": "Goiânia",
    "janela_dias": 90,
    "expandir_top": 5
  }'
```

**Se omitir `data_partida`:** modo aberto — não envie `data_retorno`.

| Campo | Conteúdo |
|---|---|
| `por_data[]` | Uma linha por dia: `data`, `preco`, IATAs + `oferta` (voo completo ou `null`) |
| `ofertas[]` | Lista plana das ofertas expandidas (mesmo JSON de `por_data[].oferta`) |
| `total` | Quantidade de itens em `ofertas[]` |

Controle de expansão: [`expandir_top`](#busca-aberta--como-ler-a-resposta).

#### Busca por estado

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/por-local \
  -H "Content-Type: application/json" \
  -d '{
    "origem_tipo": "estado",
    "origem_valor": "Espírito Santo",
    "destino_tipo": "estado",
    "destino_valor": "GO",
    "data_partida": "2026-08-10"
  }'
```

#### Ida e volta

```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/por-local \
  -H "Content-Type: application/json" \
  -d '{
    "origem_tipo": "cidade",
    "origem_valor": "Vitória",
    "destino_tipo": "cidade",
    "destino_valor": "São Paulo",
    "data_partida": "2026-08-10",
    "data_retorno": "2026-08-14"
  }'
```

#### Campos da requisição

| Campo | Tipo | Obrig. | Padrão | Se omitir | Se inválido |
|---|---|---|---|---|---|
| `origem_tipo` | `string` | Não | `"cidade"` | Assume cidade | Valor fora do enum → `422` |
| `origem_valor` | `string` | **Sim** | — | `422` | Cidade/estado sem aeroporto → `422` |
| `destino_tipo` | `string` | Não | `"cidade"` | Assume cidade | — |
| `destino_valor` | `string` | **Sim** | — | `422` | Sem aeroporto resolvível → `422` |
| `data_partida` | `string` | Não | `null` | Modo **aberto** | Formato inválido → `422` |
| `data_retorno` | `string` | Não | `null` | Só ida | Sem `data_partida` → `422`; anterior à ida → `422` |
| `janela_dias` | `int` | Não | `90` (env) | Usa `OPEN_SEARCH_WINDOW_DAYS` | 1–180; só modo aberto |
| `expandir_top` | `int\|null` | Não | `null` (todas) | Expande todas as datas | `0` = só resumo; max `180`; só modo aberto |
| `adultos` | `int` | Não | `1` | 1 adulto | 1–9 |
| `criancas` | `int` | Não | `0` | Sem crianças | 0–8; só modo `data_fixa` |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | — |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | `"NON_STOP"` pode zerar ofertas |
| `ordenar_por` | `string` | Não | `"CHEAPEST"` | Por preço | Só modo `data_fixa` |
| `limite_top` | `int` | Não | `20` | 20 ofertas/combo | 1–50; só modo `data_fixa` |

#### Resolução de cidades — exemplos

| `*_valor` | Aeroportos resolvidos | Observação |
|---|---|---|
| `"Vitória"` | `VIX` | Uma cidade, um aeroporto principal |
| `"São Paulo"` | `GRU`, `CGH` | VCP fica em `"Campinas"`, não em São Paulo |
| `"Campinas"` | `VCP` | Viracopos |
| `"Goiânia"` | `GYN` | — |
| `"GRU"` (tipo `aeroporto`) | `GRU` | IATA direto |

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `origem_buscada` / `destino_buscado` | `string` | Texto enviado pelo cliente |
| `modo_busca` | `string` | `"data_fixa"` ou `"aberta"` |
| `data_partida` / `data_retorno` | `string\|null` | Preenchidos no modo `data_fixa` |
| `data_inicio` / `data_fim` | `string\|null` | Preenchidos no modo `aberta` |
| `janela_dias` | `int\|null` | Preenchido no modo `aberta` |
| `moeda` | `string` | Moeda |
| `por_data` | `array` | Calendário de preços (modo `aberta`); vazio no modo `data_fixa` |
| `ofertas` | `array` | Ofertas completas (`OfertaBuscaPorLocalSaida`), por preço |
| `total` | `int` | Quantidade em `ofertas` |
| `melhor_oferta` | `object\|null` | Atalho — oferta mais barata |
| `aeroporto_origem_usado` | `string\|null` | IATA origem da melhor oferta |
| `aeroporto_destino_usado` | `string\|null` | IATA destino da melhor oferta |
| `todas_combinacoes` | `array` | Resumo por par IATA testado |

`por_data[]` (modo aberto):

| Campo | Descrição |
|---|---|
| `data` | Data ISO |
| `preco` | Menor preço naquela data (entre todos os pares IATA) |
| `moeda` | Moeda |
| `aeroporto_origem_iata` | Par vencedor — origem |
| `aeroporto_destino_iata` | Par vencedor — destino |
| `oferta` | `OfertaBuscaPorLocalSaida` completa (`trechos`, `rota_iata`, `url_busca_google_flights`, etc.) ou `null` se não expandida |

`OfertaBuscaPorLocalSaida` = `OfertaVooSaida` + campos:

| Campo extra | Descrição |
|---|---|
| `aeroporto_origem_iata` | IATA origem desta oferta |
| `aeroporto_destino_iata` | IATA destino desta oferta |

`todas_combinacoes[]`:

| Campo | Descrição |
|---|---|
| `origem_iata` / `destino_iata` | Par testado |
| `preco_minimo` | Menor preço daquele par (`null` se falhou) |
| `sucesso` | `true` / `false` |
| `mensagem_erro` | Preenchido se `sucesso: false` |

```json
{
  "origem_buscada": "Vitória",
  "destino_buscado": "Goiânia",
  "modo_busca": "data_fixa",
  "data_partida": "2026-08-10",
  "data_retorno": null,
  "data_inicio": null,
  "data_fim": null,
  "janela_dias": null,
  "moeda": "BRL",
  "por_data": [],
  "total": 120,
  "ofertas": ["..."],
  "melhor_oferta": { "...": "igual à oferta mais barata" },
  "aeroporto_origem_usado": "VIX",
  "aeroporto_destino_usado": "GYN",
  "todas_combinacoes": ["..."]
}
```

Exemplo — modo **aberto** (com `oferta` expandida):

```json
{
  "origem_buscada": "Vitória",
  "destino_buscado": "Curitiba",
  "modo_busca": "aberta",
  "data_inicio": "2026-08-02",
  "data_fim": "2026-11-01",
  "janela_dias": 90,
  "moeda": "BRL",
  "por_data": [
    {
      "data": "2026-09-01",
      "preco": 400.0,
      "moeda": "BRL",
      "aeroporto_origem_iata": "VIX",
      "aeroporto_destino_iata": "CWB",
      "oferta": {
        "preco": 400.0,
        "direto": false,
        "com_conexao": true,
        "rota_iata": [
          { "iata": "VIX", "cidade": "Vitória" },
          { "iata": "CWB", "cidade": "Curitiba" }
        ],
        "url_busca_google_flights": "https://www.google.com/travel/flights?q=...",
        "trechos": ["..."],
        "aeroporto_origem_iata": "VIX",
        "aeroporto_destino_iata": "CWB"
      }
    }
  ],
  "total": 1,
  "ofertas": ["...igual a por_data[0].oferta..."],
  "melhor_oferta": { "preco": 400.0, "...": "..." },
  "todas_combinacoes": ["..."]
}
```

---

### GET /api/v1/aeroportos

Autocomplete e filtros sobre ~7.800 aeroportos. Todos os parâmetros são **opcionais**.

#### Sem filtros (primeiros 20)

```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos"
```

**Se omitir tudo:** retorna até 20 aeroportos (ordem interna do índice).

#### Autocomplete por texto

```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos?busca=vitoria&limite=5"
```

**`busca`:** match parcial em IATA, nome, cidade ou estado. Ignora acentos (`vitoria` = `Vitória`).

#### Filtro estrito por cidade

```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos?cidade=Goi%C3%A2nia"
```

**Diferença `busca` vs `cidade`:** `busca` é amplo; `cidade` exige match exato no nome da cidade.

#### Filtro por estado + só principais

```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos?estado=GO&apenas_principais=true"
```

#### Parâmetros

| Parâmetro | Tipo | Obrig. | Padrão | Se omitir | Se inválido |
|---|---|---|---|---|---|
| `busca` | `string` | Não | `null` | Sem filtro textual | String vazia → `422` |
| `cidade` | `string` | Não | `null` | — | String vazia → `422` |
| `estado` | `string` | Não | `null` | — | Aceita `"GO"` ou `"Goiás"` |
| `pais` | `string` | Não | `null` | — | — |
| `apenas_principais` | `bool` | Não | `false` | Inclui secundários | — |
| `limite` | `int` | Não | `20` | Máx 20 resultados | 1–100 |

Filtros **combinam** (AND): `?cidade=São Paulo&apenas_principais=true`.

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `total` | `int` | Total encontrado (antes do limite) |
| `aeroportos` | `array` | Até `limite` itens |

`aeroportos[]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `codigo_iata` | `string` | IATA |
| `nome` | `string` | Nome do aeroporto |
| `cidade` | `string\|null` | Cidade |
| `estado` | `string\|null` | UF ou região |
| `pais` | `string\|null` | País |
| `principal` | `bool` | Aeroporto comercial principal |
| `descricao_curta` | `string\|null` | Texto de disambiguação (ex: GRU vs CGH) |

```json
{
  "total": 2,
  "aeroportos": [
    {
      "codigo_iata": "GRU",
      "nome": "Guarulhos - Governador Andre Franco Montoro International Airport",
      "cidade": "São Paulo",
      "estado": "SP",
      "pais": "Brasil",
      "principal": true,
      "descricao_curta": "Aeroporto Internacional de Guarulhos — maior hub de voos nacionais e internacionais de SP"
    },
    {
      "codigo_iata": "CGH",
      "nome": "Congonhas Airport",
      "cidade": "São Paulo",
      "estado": "SP",
      "pais": "Brasil",
      "principal": true,
      "descricao_curta": "Aeroporto de Congonhas — próximo ao centro de SP, foco em ponte aérea e voos nacionais"
    }
  ]
}
```

---

### GET /api/v1/aeroportos/{codigo_iata}

Detalhe de um aeroporto por IATA.

```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos/GRU"
```

| Parâmetro | Obrig. | Se inválido |
|---|---|---|
| `codigo_iata` (path) | **Sim** | IATA inexistente → `404` |

#### Resposta `200`

Mesmo schema de um item de `aeroportos[]`.

#### Resposta `404`

```json
{
  "error": "Aeroporto com código IATA 'ZZZ' não encontrado."
}
```

---

### GET /api/v1/cidades

Autocomplete e busca exclusiva de cidades e estados (UF).

Aliases suportados:
- `GET /api/v1/cidades`
- `GET /api/v1/cities`
- `GET /api/v1/cidades/buscar`
- `GET /api/v1/cities/search`

Exemplo de uso:

```bash
curl "http://127.0.0.1:12000/api/v1/cidades?busca=são&limite=8"
curl "http://127.0.0.1:12000/api/v1/cities/search?query=GO"
```

#### Parâmetros da Query (Query Params)

| Parâmetro | Tipo | Obrigatório | Valor Padrão | Descrição |
|---|---|---|---|---|
| `busca` / `query` / `q` | `string` | Não | `null` | Busca por nome da cidade ou estado/UF (insensível a acentos/caixa) |
| `estado` / `uf` | `string` | Não | `null` | Filtro estrito por sigla UF ou nome do estado (ex: `SP`, `GO`, `Goiás`) |
| `pais` | `string` | Não | `null` | Filtro por país (ex: `Brasil`) |
| `limite` | `int` | Não | `20` | Quantidade máxima de resultados (1 a 100) |

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `total` | `int` | Total de cidades encontradas |
| `cidades` | `array` | Lista de cidades até o limite especificado |

Cada item em `cidades[]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | `string` | Nome oficial da cidade (ex: `"São Paulo"`, `"Goiânia"`) |
| `estado` | `string\|null` | Sigla da UF/Estado (ex: `"SP"`, `"GO"`) |
| `estado_nome` | `string\|null` | Nome completo do estado (ex: `"São Paulo"`, `"Goiás"`) |
| `pais` | `string` | País da cidade (ex: `"Brasil"`) |

Exemplo de JSON retornado:

```json
{
  "total": 2,
  "cidades": [
    {
      "nome": "Caldas Novas",
      "estado": "GO",
      "estado_nome": "Goiás",
      "pais": "Brasil"
    },
    {
      "nome": "Goiânia",
      "estado": "GO",
      "estado_nome": "Goiás",
      "pais": "Brasil"
    }
  ]
}
```

---

## Exemplos de integração

### PHP (Symfony / Guzzle)

```php
$client = new \GuzzleHttp\Client(['base_uri' => 'http://127.0.0.1:12000']);

// Busca só ida — campos mínimos
$response = $client->post('/api/v1/buscar', [
    'headers' => [
        'X-Internal-Token' => getenv('FLIGHTS_API_INTERNAL_TOKEN'),
        'Content-Type'     => 'application/json',
    ],
    'json' => [
        'origem'       => 'VIX',
        'destino'      => 'GRU',
        'data_partida' => '2026-08-10',
    ],
]);

$dados = json_decode($response->getBody()->getContents(), true);
$ofertas = $dados['ofertas']; // array — pode ser vazio

// Alerta sem data — calendário de preços por cidade
$response = $client->post('/api/v1/buscar/por-local', [
    'headers' => ['Content-Type' => 'application/json'],
    'json' => [
        'origem_valor'  => 'Vitória',
        'destino_valor' => 'Goiânia',
        'janela_dias'   => 90,
        'expandir_top'  => 0,
    ],
]);
$dados = json_decode($response->getBody()->getContents(), true);
foreach ($dados['por_data'] as $dia) {
    echo $dia['data'] . ' — R$ ' . $dia['preco'];
    if ($dia['oferta']) {
        echo $dia['oferta']['url_busca_google_flights'];
        echo $dia['oferta']['rota_iata'][0]['cidade']; // Vitória
    }
}

// Alerta sem data — endpoint dedicado
$response = $client->post('/api/v1/buscar/aberta', [
    'headers' => ['Content-Type' => 'application/json'],
    'json' => [
        'origem_valor'  => 'Vitória',
        'destino_valor' => 'Goiânia',
        'expandir_top'  => 3,
    ],
]);
```

### JavaScript (fetch)

```javascript
const resposta = await fetch('http://127.0.0.1:12000/api/v1/buscar/por-local', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Internal-Token': process.env.FLIGHTS_API_TOKEN,
  },
  body: JSON.stringify({
    origem_valor: 'Vitória',
    destino_valor: 'Goiânia',
    // data_partida omitida = modo aberto
    janela_dias: 90,
    expandir_top: 5,
  }),
});

const dados = await resposta.json();
if (dados.modo_busca === 'aberta') {
  dados.por_data.forEach((dia) => {
    console.log(dia.data, dia.preco, dia.oferta?.url_busca_google_flights);
  });
}
```

---

## Referência cruzada

| Documento | Conteúdo |
|---|---|
| [DOCUMENTACAO_TECNICA.md](./DOCUMENTACAO_TECNICA.md) | Estrutura de pastas e arquivos |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Decisões de arquitetura |
| [README.md](../README.md) | Setup rápido |
