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
2. [Campos opcionais e padrões](#campos-opcionais-e-padrões)
3. [Erros e códigos HTTP](#erros-e-códigos-http)
4. [Enums aceitos](#enums-aceitos)
5. [Modelos de resposta compartilhados](#modelos-de-resposta-compartilhados)
6. [Endpoints](#endpoints)
   - [GET /saude](#get-saude)
   - [POST /api/v1/buscar](#post-apiv1buscar)
   - [POST /api/v1/buscar/janela](#post-apiv1buscarjanela)
   - [POST /api/v1/buscar/por-local](#post-apiv1buscarpor-local)
   - [GET /api/v1/aeroportos](#get-apiv1aeroportos)
   - [GET /api/v1/aeroportos/{codigo_iata}](#get-apiv1aeroportoscodigo_iata)
   - [GET /api/v1/cidades](#get-apiv1cidades)
7. [Exemplos de integração](#exemplos-de-integração)

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
| Heatmap / alerta por **intervalo de datas** | `POST /api/v1/buscar/janela` |
| Usuário digitou **cidade ou estado** (sem saber IATA) | `POST /api/v1/buscar/por-local` |
| Autocomplete de aeroportos | `GET /api/v1/aeroportos` |
| Autocomplete exclusivo de cidades/estados | `GET /api/v1/cidades` ou `GET /api/v1/cities` |

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

Presente em `/buscar`, `/buscar/janela` (`mais_baratas_expandidas`) e `/buscar/por-local` (`ofertas`).

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

**Não use** para exibir "preço agora" ao usuário sem expandir a data vencedora via `/buscar`.

#### Requisição mínima

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

**Se omitir `expandir_top`:** padrão `1` — expande a data mais barata com oferta completa.

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
| `data_inicio` | `string` | **Sim** | — | `422` | Formato inválido → `422` |
| `data_fim` | `string` | **Sim** | — | `422` | Anterior a `data_inicio` → `422` |
| `adultos` | `int` | Não | `1` | 1 adulto | Fora de 1–9 → `422` |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | — |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | — |
| `expandir_top` | `int` | Não | `1` | Expande 1 data | `0` = sem expansão; max `10`; fora do range → `422` |

> Janela **não suporta** `data_retorno` — sempre busca só ida por dia.

#### Resposta `200`

| Campo | Tipo | Descrição |
|---|---|---|
| `origem` / `destino` | `string` | IATAs |
| `data_inicio` / `data_fim` | `string` | Intervalo |
| `moeda` | `string` | Moeda |
| `por_data` | `array` | `{ data, preco, moeda }` por dia, ordenado por preço |
| `mais_baratas_expandidas` | `array` | `OfertaVooSaida` das N datas mais baratas |

```json
{
  "origem": "VIX",
  "destino": "GRU",
  "data_inicio": "2026-08-02",
  "data_fim": "2026-08-08",
  "moeda": "BRL",
  "por_data": [
    { "data": "2026-08-05", "preco": 303.0, "moeda": "BRL" },
    { "data": "2026-08-06", "preco": 412.0, "moeda": "BRL" }
  ],
  "mais_baratas_expandidas": [
    {
      "preco": 303.0,
      "direto": true,
      "rota_iata": [
        { "iata": "VIX", "cidade": "Vitória" },
        { "iata": "GRU", "cidade": "São Paulo" }
      ],
      "trechos": ["..."]
    }
  ]
}
```

---

### POST /api/v1/buscar/por-local

Busca por **cidade, estado ou aeroporto** — o usuário não precisa saber IATA.

#### Fluxo interno

1. Resolve origem e destino em até **3 aeroportos principais** cada
2. Gera combinações (ex: Vitória × São Paulo → VIX→GRU, VIX→CGH)
3. Busca em **paralelo** (até 4 threads)
4. **Cache** de 5 min por par IATA+data
5. Retorna **todas as ofertas** de todas as combinações, ordenadas por preço

#### Requisição mínima (cidade → cidade)

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
| `data_partida` | `string` | **Sim** | — | `422` | Formato inválido → `422` |
| `data_retorno` | `string` | Não | `null` | Só ida | Anterior à partida → `422` |
| `adultos` | `int` | Não | `1` | 1 adulto | 1–9 |
| `criancas` | `int` | Não | `0` | Sem crianças | 0–8 |
| `classe_cabine` | `string` | Não | `"ECONOMY"` | Econômica | — |
| `maximo_escalas` | `string` | Não | `"ANY"` | Aceita conexões | `"NON_STOP"` pode zerar ofertas |
| `ordenar_por` | `string` | Não | `"CHEAPEST"` | Por preço | — |
| `limite_top` | `int` | Não | `20` | 20 ofertas/combo | 1–50 |

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
| `data_partida` / `data_retorno` | `string` | Datas da busca |
| `moeda` | `string` | Moeda |
| `ofertas` | `array` | Todas as ofertas (`OfertaBuscaPorLocalSaida`), por preço |
| `total` | `int` | Quantidade em `ofertas` |
| `melhor_oferta` | `object\|null` | Atalho — oferta mais barata |
| `aeroporto_origem_usado` | `string\|null` | IATA origem da melhor oferta |
| `aeroporto_destino_usado` | `string\|null` | IATA destino da melhor oferta |
| `todas_combinacoes` | `array` | Resumo por par IATA testado |

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
  "data_partida": "2026-08-10",
  "data_retorno": null,
  "moeda": "BRL",
  "total": 120,
  "ofertas": [
    {
      "preco": 693.0,
      "direto": false,
      "com_conexao": true,
      "rota_iata": [
        { "iata": "VIX", "cidade": "Vitória" },
        { "iata": "VCP", "cidade": "Campinas" },
        { "iata": "GYN", "cidade": "Goiânia" }
      ],
      "aeroportos_conexao": [{ "iata": "VCP", "cidade": "Campinas" }],
      "aeroporto_origem_iata": "VIX",
      "aeroporto_destino_iata": "GYN",
      "trechos": ["..."]
    }
  ],
  "melhor_oferta": { "...": "igual à oferta mais barata" },
  "aeroporto_origem_usado": "VIX",
  "aeroporto_destino_usado": "GYN",
  "todas_combinacoes": [
    { "origem_iata": "VIX", "destino_iata": "GYN", "preco_minimo": 693.0, "sucesso": true, "mensagem_erro": null }
  ]
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

// Busca por cidade
$response = $client->post('/api/v1/buscar/por-local', [
    'headers' => ['Content-Type' => 'application/json'],
    'json' => [
        'origem_valor'  => 'Vitória',
        'destino_valor' => 'Goiânia',
        'data_partida'  => '2026-08-10',
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
    origem_tipo: 'cidade',
    origem_valor: 'Vitória',
    destino_tipo: 'cidade',
    destino_valor: 'São Paulo',
    data_partida: '2026-08-10',
    maximo_escalas: 'NON_STOP', // opcional — só diretos
  }),
});

if (resposta.status === 422) {
  const erro = await resposta.json();
  // erro.detail (validação) ou erro.error (regra de negócio)
}

const dados = await resposta.json();
console.log(dados.total, dados.ofertas[0]?.preco);
```

---

## Referência cruzada

| Documento | Conteúdo |
|---|---|
| [DOCUMENTACAO_TECNICA.md](./DOCUMENTACAO_TECNICA.md) | Estrutura de pastas e arquivos |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Decisões de arquitetura |
| [README.md](../README.md) | Setup rápido |
