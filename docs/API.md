# 📖 Especificação Técnica e Manual da API REST

A **Flights API** (`voobarato-flights-api`) é um microsserviço HTTP RESTful em Python (FastAPI) que provê barramento de comunicação unificado entre o ecossistema Voo Barato (Symfony Backend, Apps Web/Mobile) e a API interna do Google Flights.

---

## 🌐 Informações de Conexão

- **Host Base**: `http://127.0.0.1:12000`
- **Protocolo**: HTTP / JSON (UTF-8)
- **Convenção de Nomes**: Todos os campos JSON de requisição e resposta são padronizados em **Português (PT-BR)**.
- **Swagger / OpenAPI**: `http://127.0.0.1:12000/docs`

---

## 🔒 Autenticação

Para rotas protegidas (todas sob o prefixo `/api/v1/`), é necessário fornecer o cabeçalho HTTP de autenticação interna:

```http
X-Internal-Token: voobarato_secret_token_12345
```

> [!NOTE]
> Se o token for omitido ou incorreto quando configurado no ambiente (`FLIGHTS_API_INTERNAL_TOKEN`), a API responderá com `401 Unauthorized`:
> ```json
> {
>   "error": "nao_autorizado"
> }
> ```

---

## 📋 Enums e Valores Válidos

### 1. Classes de Cabine (`classe_cabine`)
- `"ECONOMY"`: Econômica (Padrão)
- `"PREMIUM_ECONOMY"`: Econômica Premium
- `"BUSINESS"`: Executiva
- `"FIRST"`: Primeira Classe

### 2. Máximo de Escalas (`maximo_escalas`)
- `"ANY"`: Qualquer quantidade de escalas (Padrão)
- `"NON_STOP"`: Apenas voos diretos (sem escalas)
- `"ONE_STOP"`: No máximo 1 escala
- `"TWO_PLUS_STOPS"`: No máximo 2 escalas

### 3. Ordenação (`ordenar_por`)
- `"CHEAPEST"`: Ordenar por menor preço (Padrão)
- `"BEST"`: Melhor custo-benefício
- `"TOP_FLIGHTS"`: Voos mais populares
- `"DURATION"`: Menor duração
- `"DEPARTURE_TIME"`: Horário de partida
- `"ARRIVAL_TIME"`: Horário de chegada

---

## 📦 Modelo `OfertaVooSaida`

Presente em `/buscar`, `/buscar/janela` (expandidas) e `/buscar/por-local`.

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `preco` | `float` | Preço total da oferta (ida ou ida+volta conforme a busca) |
| `moeda` | `string` | Moeda (ex: `"BRL"`) |
| `duracao_minutos` | `integer` | Duração total em minutos |
| `escalas` | `integer` | Quantidade de escalas |
| `direto` | `boolean` | `true` se voo sem escalas |
| `com_conexao` | `boolean` | `true` se passa por hub(s) intermediários |
| `rota_iata` | `array` | Sequência da rota: `[{ "iata": "VIX", "cidade": "Vitória" }, ...]` |
| `aeroportos_conexao` | `array` | Hubs intermediários (mesmo formato de `rota_iata`) |
| `companhia_principal` | `string` | Companhia principal |
| `trechos` | `array` | Pernas do voo (ver abaixo) |
| `url_busca_google_flights` | `string` | Link de conferência no Google Flights (`one way` ou `returning` conforme a busca) |
| `encontrado_em` | `datetime` | Timestamp UTC da consulta |
| `fonte` | `string` | Sempre `"fli"` |

### Trecho (`trechos[]`)

| Campo | Descrição |
| :--- | :--- |
| `iata_partida` / `iata_chegada` | Códigos IATA |
| `aeroporto_partida` / `aeroporto_chegada` | Nome completo do aeroporto |
| `data_hora_partida` / `data_hora_chegada` | Horário local naive (sem `Z`) |
| `numero_voo`, `aeronave`, `companhia_aerea` | Detalhes operacionais |

> [!NOTE]
> **Preço só ida vs ida e volta**: com `data_retorno: null`, o preço é **só da ida**. No Google Flights, o mesmo trecho pode aparecer como metade do preço de um pacote ida e volta. A URL gerada inclui `one way` ou `returning YYYY-MM-DD` para bater com o tipo de busca.

> [!NOTE]
> **Rotas com conexão**: com `maximo_escalas: "ANY"` (padrão), o Google Flights monta itinerários com escala automaticamente (ex: VIX→GYN via VCP). Voos diretos e com conexão coexistem; a lista vem ordenada por preço.

---

## 📌 Guia de Endpoints

### 1. `GET /saude`
Verificação de integridade da API (Liveness / Readiness Check para Docker e Kubernetes). Rota pública.

#### 💻 Exemplo `curl`:
```bash
curl -X GET http://127.0.0.1:12000/saude
```

#### 📤 Resposta `200 OK`:
```json
{
  "status": "ok",
  "servico": "voobarato-flights-api",
  "versao": "1.0.0"
}
```

---

### 2. `POST /api/v1/buscar`
Busca por voos e ofertas em **data exata**. Deve ser utilizada para exibição direta ao usuário ou para disparar alertas e notificações em tempo real.

#### 💻 Exemplo `curl` (Ida e Volta - Vitória para Guarulhos):
```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: voobarato_secret_token_12345" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_partida": "2026-08-10",
    "data_retorno": "2026-08-17",
    "adultos": 1,
    "criancas": 0,
    "classe_cabine": "ECONOMY",
    "maximo_escalas": "ANY",
    "ordenar_por": "CHEAPEST",
    "limite_top": 3
  }'
```

#### 💻 Exemplo `curl` (Só Ida):
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

#### 📦 Campos de Requisição (Request Payload):
| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `origem` | `string` | Sim | Código IATA de 3 letras da origem (ex: `"VIX"`) |
| `destino` | `string` | Sim | Código IATA de 3 letras do destino (ex: `"GRU"`) |
| `data_partida` | `string` | Sim | Data de partida no formato ISO `YYYY-MM-DD` |
| `data_retorno` | `string` | Não | Data de retorno no formato ISO `YYYY-MM-DD` (omitir para só ida) |
| `adultos` | `integer` | Não | Quantidade de passageiros adultos (mín: 1, máx: 9, padrão: 1) |
| `criancas` | `integer` | Não | Quantidade de crianças (mín: 0, máx: 9, padrão: 0) |
| `classe_cabine` | `string` | Não | Enum da cabine (padrão: `"ECONOMY"`) |
| `maximo_escalas` | `string` | Não | Enum de escalas (padrão: `"ANY"`) |
| `ordenar_por` | `string` | Não | Enum de ordenação (padrão: `"CHEAPEST"`) |
| `limite_top` | `integer` | Não | Quantidade máxima de ofertas (mín: 1, máx: 50, padrão: 10) |

> [!WARNING]
> **Fuso Horário de Partida e Chegada (Hora Local do Aeroporto)**:
> Os campos `data_hora_partida` e `data_hora_chegada` nos trechos de voo retornam o **horário local de relógio de parede do aeroporto correspondente** (`ISO 8601 naive`, sem timezone `Z`).
> - Exemplo: `"data_hora_partida": "2026-08-10T14:30:00"` (significa 14:30 no horário local do aeroporto de origem).
> - Se o consumidor precisar realizar comparações absolutas entre voos ou calcular horas até o voo, deve resolver o timezone do aeroporto a partir do seu `codigo_iata`.

#### 📤 Resposta `200 OK`:
```json
{
  "origem": "VIX",
  "destino": "GRU",
  "data_partida": "2026-08-10",
  "data_retorno": "2026-08-17",
  "moeda": "BRL",
  "total": 1,
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
          "nome_companhia_aerea": "Gol",
          "numero_voo": "1387",
          "data_hora_partida": "2026-08-10T18:40:00",
          "data_hora_chegada": "2026-08-10T20:20:00",
          "duracao_minutos": 100,
          "aeronave": "Boeing 737",
          "companhia_operadora": null
        }
      ],
      "url_busca_google_flights": "https://www.google.com/travel/flights?q=Flights+from+VIX+to+GRU+on+2026-08-10+one+way&hl=pt-BR&gl=BR&curr=BRL",
      "encontrado_em": "2026-07-31T10:30:00Z",
      "fonte": "fli"
    }
  ]
}
```

---

### 3. `POST /api/v1/buscar/janela`
Busca de oportunidades em uma **janela de datas** (intervalo). Retorna o preço mínimo por dia (`por_data`) e expande as $N$ datas mais baratas (`mais_baratas_expandidas`).

#### 💻 Exemplo `curl`:
```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/janela \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: voobarato_secret_token_12345" \
  -d '{
    "origem": "VIX",
    "destino": "GRU",
    "data_inicio": "2026-08-02",
    "data_fim": "2026-08-08",
    "adultos": 1,
    "expandir_top": 1
  }'
```

#### 📦 Campos de Requisição (Request Payload):
| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `origem` | `string` | Sim | Código IATA da origem (ex: `"VIX"`) |
| `destino` | `string` | Sim | Código IATA do destino (ex: `"GRU"`) |
| `data_inicio` | `string` | Sim | Data inicial do intervalo no formato `YYYY-MM-DD` |
| `data_fim` | `string` | Sim | Data final do intervalo no formato `YYYY-MM-DD` |
| `adultos` | `integer` | Não | Quantidade de passageiros adultos (padrão: 1) |
| `expandir_top` | `integer` | Não | Quantidade de datas mais baratas para fazer a busca profunda completa (mín: 0, máx: 5, padrão: 1) |

#### 📤 Resposta `200 OK`:
```json
{
  "origem": "VIX",
  "destino": "GRU",
  "data_inicio": "2026-08-02",
  "data_fim": "2026-08-08",
  "moeda": "BRL",
  "por_data": [
    { "data": "2026-08-05", "preco": 303.00, "moeda": "BRL" },
    { "data": "2026-08-06", "preco": 412.00, "moeda": "BRL" },
    { "data": "2026-08-07", "preco": 550.00, "moeda": "BRL" }
  ],
  "mais_baratas_expandidas": [
    {
      "preco": 303.00,
      "moeda": "BRL",
      "duracao_minutos": 100,
      "escalas": 0,
      "companhia_principal": "LATAM",
      "nome_companhia_principal": "LATAM Airlines",
      "trechos": [ ... ],
      "url_busca_google_flights": "https://www.google.com/travel/flights...",
      "encontrado_em": "2026-07-31T10:30:00Z",
      "fonte": "fli"
    }
  ]
}
```

---

### 4. `POST /api/v1/buscar/por-local`
Busca de voos por **localidade (cidade, estado ou aeroporto)**. A API resolve aeroportos elegíveis, gera o produto cartesiano das combinações, roda buscas em **paralelo (até 4 workers)** com **cache em memória (5 min)** e retorna **todas as ofertas** de todas as combinações, ordenadas por preço.

> [!NOTE]
> Resolução por **cidade** faz match exato no nome (ex: `"São Paulo"` → GRU + CGH; Viracopos/VCP fica em `"Campinas"`).

#### 💻 Exemplo `curl` (Vitória para Goiânia):
```bash
curl -X POST http://127.0.0.1:12000/api/v1/buscar/por-local \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: voobarato_secret_token_12345" \
  -d '{
    "origem_tipo": "cidade",
    "origem_valor": "Vitória",
    "destino_tipo": "cidade",
    "destino_valor": "Goiânia",
    "data_partida": "2026-08-10"
  }'
```

#### 📦 Campos de Requisição (Request Payload):
| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `origem_tipo` | `string` | Sim | `"cidade"`, `"estado"` ou `"aeroporto"` |
| `origem_valor` | `string` | Sim | Nome da cidade, estado (ex: `"ES"`) ou IATA |
| `destino_tipo` | `string` | Sim | `"cidade"`, `"estado"` ou `"aeroporto"` |
| `destino_valor` | `string` | Sim | Nome da cidade, estado ou IATA |
| `data_partida` | `string` | Sim | Data de partida `YYYY-MM-DD` |
| `data_retorno` | `string` | Não | Data de retorno `YYYY-MM-DD` (omitir = só ida) |
| `limite_top` | `integer` | Não | Ofertas por combinação IATA (padrão: 20, máx: 50) |
| `maximo_escalas` | `string` | Não | Padrão `"ANY"` |

#### 📤 Resposta `200 OK`:
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
      "escalas": 1,
      "direto": false,
      "com_conexao": true,
      "rota_iata": [
        { "iata": "VIX", "cidade": "Vitória" },
        { "iata": "VCP", "cidade": "Campinas" },
        { "iata": "GYN", "cidade": "Goiânia" }
      ],
      "aeroportos_conexao": [
        { "iata": "VCP", "cidade": "Campinas" }
      ],
      "aeroporto_origem_iata": "VIX",
      "aeroporto_destino_iata": "GYN",
      "trechos": [ "..." ]
    }
  ],
  "melhor_oferta": { "...": "mesma estrutura da oferta mais barata" },
  "aeroporto_origem_usado": "VIX",
  "aeroporto_destino_usado": "GYN",
  "todas_combinacoes": [
    { "origem_iata": "VIX", "destino_iata": "GYN", "preco_minimo": 693.0, "sucesso": true }
  ]
}
```

| Campo | Descrição |
| :--- | :--- |
| `ofertas` | Todas as ofertas de todas as combinações, ordenadas por preço |
| `melhor_oferta` | Atalho para a oferta mais barata (compatibilidade) |
| `todas_combinacoes` | Resumo por par IATA (menor preço de cada combinação) |
| `aeroporto_origem_iata` / `aeroporto_destino_usado` | Par IATA da oferta mais barata |

---

### 5. `GET /api/v1/aeroportos`
Consulta e busca de aeroportos mundiais (7.835 cadastrados) com inteligência de autocomplete, normalização de acentos, campo de `descricao_curta` para disambiguação e filtros avançados.

#### 📦 Parâmetros de Query String:
| Parâmetro | Tipo | Exemplo | Descrição |
| :--- | :--- | :--- | :--- |
| `busca` | `string` | `?busca=vitoria` ou `?busca=goias` | Busca aberta textual por IATA, nome do aeroporto, cidade ou estado (sem diferenciar acentos) |
| `cidade` | `string` | `?cidade=Goiânia` | Filtro estrito por nome de cidade |
| `estado` | `string` | `?estado=GO` ou `?estado=Goiás` | Filtro estrito por estado (sigla UF ou nome completo) |
| `pais` | `string` | `?pais=Brasil` | Filtro estrito por país |
| `apenas_principais` | `boolean` | `?apenas_principais=true` | Se `true`, retorna apenas aeroportos comerciais principais (`principal: true`) |
| `limite` | `integer` | `?limite=10` | Limite de resultados a retornar (mín: 1, máx: 100, padrão: 20) |

#### 💻 Exemplo 1: Busca Aberta por Cidade com Acento ("Vitória")
```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos?busca=vitoria&limite=2"
```

#### 📤 Resposta `200 OK`:
```json
{
  "total": 2,
  "aeroportos": [
    {
      "codigo_iata": "VIX",
      "nome": "Eurico de Aguiar Salles Airport",
      "cidade": "Vitória",
      "estado": "ES",
      "pais": "Brasil",
      "principal": true
    },
    {
      "codigo_iata": "VDC",
      "nome": "Glauber de Andrade Rocha Airport",
      "cidade": "Vitória da Conquista",
      "estado": "BA",
      "pais": "Brasil",
      "principal": true
    }
  ]
}
```

#### 💻 Exemplo 2: Busca por Estado ("Goiás" / "GO")
```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos?estado=GO&apenas_principais=true"
```

#### 📤 Resposta `200 OK`:
```json
{
  "total": 2,
  "aeroportos": [
    {
      "codigo_iata": "CLV",
      "nome": "Caldas Novas Airport",
      "cidade": "Caldas Novas",
      "estado": "GO",
      "pais": "Brasil",
      "principal": true
    },
    {
      "codigo_iata": "GYN",
      "nome": "Santa Genoveva Airport",
      "cidade": "Goiânia",
      "estado": "GO",
      "pais": "Brasil",
      "principal": true
    }
  ]
}
```

---

### 6. `GET /api/v1/aeroportos/{codigo_iata}`
Consulta direta dos detalhes de um aeroporto a partir do código IATA de 3 letras (ex: `GRU`, `VIX`, `BSB`).

#### 💻 Exemplo `curl`:
```bash
curl "http://127.0.0.1:12000/api/v1/aeroportos/GRU"
```

#### 📤 Resposta `200 OK`:
```json
{
  "codigo_iata": "GRU",
  "nome": "Guarulhos - Governador Andre Franco Montoro International Airport",
  "cidade": "São Paulo",
  "estado": "SP",
  "pais": "Brasil",
  "principal": true
}
```

#### 📤 Resposta `404 Not Found` (Código inexistente):
```json
{
  "error": "Aeroporto com código IATA 'ZZZ' não encontrado."
}
```

---

## 🛑 Tratamento de Erros e Códigos de Status HTTP

| Código Status | Significado | Exemplo de JSON de Retorno | Causa / Ação Recomendada |
| :--- | :--- | :--- | :--- |
| **`200 OK`** | Sucesso | `{ ... }` | Requisição processada corretamente. |
| **`401 Unauthorized`** | Não Autorizado | `{"error": "nao_autorizado"}` | O cabeçalho `X-Internal-Token` é inválido ou não foi enviado. |
| **`422 Unprocessable`** | Erro de Validação | `{"error": "data_retorno_anterior_partida"}` | Parâmetro inválido (ex: código IATA inexistente, data no passado). |
| **`404 Not Found`** | Recurso Não Encontrado | `{"error": "Aeroporto com código IATA 'XYZ' não encontrado."}` | Código IATA de aeroporto não existe na base mundial. |
| **`502 Bad Gateway`** | Falha de Comunicação | `{"error": "upstream_search_failed"}` | Instabilidade de comunicação com o Google Flights upstream. |

---

## 💻 Exemplos de Integração em Outras Linguagens

### PHP (Symfony / Guzzle Client):
```php
use GuzzleHttp\Client;

$client = new Client(['base_uri' => 'http://127.0.0.1:12000']);
$response = $client->post('/api/v1/buscar', [
    'headers' => [
        'X-Internal-Token' => 'voobarato_secret_token_12345',
        'Content-Type'     => 'application/json',
    ],
    'json' => [
        'origem'       => 'VIX',
        'destino'      => 'GRU',
        'data_partida' => '2026-08-10',
    ]
]);

$dados = json_decode($response->getBody()->getContents(), true);
```

### Node.js (Fetch API):
```javascript
const resposta = await fetch('http://127.0.0.1:12000/api/v1/buscar', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Internal-Token': 'voobarato_secret_token_12345'
  },
  body: JSON.stringify({
    origem: 'VIX',
    destino: 'GRU',
    data_partida: '2026-08-10'
  })
});

const dados = await resposta.json();
```
