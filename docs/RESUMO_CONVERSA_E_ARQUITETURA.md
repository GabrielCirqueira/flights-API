# Resumo Completo da Conversa, Contexto e Decisões de Arquitetura

Este documento consolida todo o contexto, decisões de arquitetura, correções críticas e novas funcionalidades implementadas no projeto **`voo-flights`** ao longo de nossa sessão de pair-programming.

---

## 📌 1. Diretrizes Globais e Políticas do Projeto

1. **Idioma e Nomenclatura**:
   - Todas as variáveis, rotas HTTP (`/api/v1/buscar`, `/api/v1/buscar/janela`, `/api/v1/buscar/por-local`, `/api/v1/aeroportos`, `/saude`), DTOs e campos JSON (`origem`, `destino`, `data_partida`, `data_retorno`, `cidade`, `estado`, `pais`, `principal`, `descricao_curta`, `melhor_oferta`) são **obrigatoriamente em Português (PT-BR)**.
   - Nomes de pacotes/bibliotecas externas permanecem inalterados.

2. **Manipulação de Horários (Datetimes Naive)**:
   - Os horários retornados pelo Google Flights / `fli` (`data_hora_partida` e `data_hora_chegada`) representam o **horário local de parede do aeroporto** (wall-clock time), sem timezone.
   - **Regra Rígida**: NUNCA adicionar sufixo `"Z"` nem converter para UTC, evitando confusões de fuso horário em comparações no Symfony ou em clientes consumidores.

3. **Pinagem da Biblioteca Upstream**:
   - A biblioteca `flights` foi fixada na versão `==0.9.0` no `requirements.txt` para prevenir quebras causadas por alterações na API interna reverse-engineered do Google Flights.

4. **Rastreabilidade HTTP (`X-Request-ID`)**:
   - Middleware no `app/main.py` injeta um identificador único de correlação (`X-Request-ID` / `X-Correlation-ID`) no estado da requisição, nos cabeçalhos de resposta HTTP e nos logs de exceções.

---

## 🔍 2. Problemas Identificados e Soluções Arquiteturais

### 2.1. Busca e Filtros Avançados de Aeroportos
- **Problema**: O pacote `fli` nativo só possuía um Enum básico com códigos IATA, sem metadados como cidade, estado, país ou status comercial. O endpoint `/api/v1/aeroportos` necessitava de busca inteligente por estado e cidade.
- **Solução**:
  - Implementado um dataset enriquecido com 7.835 aeroportos mundiais e mapeamento `_ESTADOS_BRASIL` (convertendo siglas como `GO` $\leftrightarrow$ `Goiás`).
  - Criado o **Startup Caching** (`_INDICE_AEROPORTOS_CACHE`), reduzindo o tempo de resposta do autocomplete de ~27ms para **sub-milissegundos (< 0.5ms)**.

---

### 2.2. Disambiguação de Aeroportos na Mesma Cidade
- **Problema**: Usuários leigos não sabem diferenciar aeroportos da mesma cidade (ex: Confins `CNF` vs Pampulha `PLU` em Belo Horizonte, ou Guarulhos `GRU` vs Congonhas `CGH` vs Viracopos `VCP` em SP).
- **Solução**:
  - Adicionado o campo **`descricao_curta`** no schema `AeroportoSaida` e em `_MAPEAMENTO_AEROPORTOS`.
  - Exemplo:
    - `CNF`: `"Aeroporto Internacional de Confins — maior hub de voos comerciais de MG"`
    - `PLU`: `"Aeroporto da Pampulha — voos executivos e regionais, poucas opções comerciais"`

---

### 2.3. Busca por Localidade (`POST /api/v1/buscar/por-local`)
- **Problema**: Usuários frequentemente pesquisam voos informando apenas a cidade ou estado de origem/destino sem saber quais aeroportos devem selecionar.
- **Solução**:
  - Criado o endpoint **`POST /api/v1/buscar/por-local`**.
  - A API resolve a localidade (ex: `"Vitória"` $\rightarrow$ `VIX`, `"São Paulo"` $\rightarrow$ `[GRU, CGH, VCP]`), gera o produto cartesiano de combinações (limitado aos 3 aeroportos principais por lado) e executa as buscas em **paralelo (ThreadPoolExecutor com até 4 workers)**.
  - Implementado um **Cache em Memória de Curto Prazo (TTL 5 minutos)** para evitar requisições duplicadas.
  - A resposta consolida o resultado apontando a **melhor oferta global** e informando explicitamente os pares de IATA utilizados (`aeroporto_origem_usado` e `aeroporto_destino_usado`).

---

### 2.4. Correção em Buscas de Ida e Volta (Round-Trip) e Ofertas Fake `0.0`
- **Problema**: Ao buscar voos com `data_retorno`, o `fli` retorna uma lista de tuplas `(voo_ida, voo_volta)`. O código antigo desmembravas as tuplas em itens individuais na lista. Como algumas opções de volta vinham sem preço individualizado (`price = None`), o mapeador antigo atribuía `preco: 0.0`, fazendo com que a volta isolada ganhasse como a "melhor oferta de R$ 0,00".
- **Solução**:
  - Refatorado o `_mapear_oferta` em `app/services/servico_fli.py` para tratar a tupla `(voo_ida, voo_volta)` como um **único objeto `OfertaVooSaida` consolidado**.
  - A oferta unificada agora contém **todos os trechos da viagem** (Ida + Volta) e o **preço total correto**.
  - Adicionado filtro estrito para **descartar combinações sem preço ou com valor zero**.

---

### 2.5. Garantia de Conexões em Rotas sem Voo Direto
- **Problema**: Cidades sem rotas diretas (ex: Vitória $\rightarrow$ Goiânia) exigem voos de conexão.
- **Solução**:
  - O parâmetro `maximo_escalas` é configurado por padrão como `"ANY"`, permitindo que o Google Flights traga automaticamente voos com 1 ou mais conexões.
  - Adicionado o teste de regressão `test_regressao_maximo_escalas_padrao_any`.

---

## 🛠️ 3. Resumo dos Endpoints da API

| Endpoint | Método | Descrição |
| :--- | :--- | :--- |
| `/saude` | `GET` | Verificação de integridade do serviço |
| `/api/v1/buscar` | `POST` | Busca pontual exata por código IATA de origem e destino |
| `/api/v1/buscar/janela` | `POST` | Busca por janela de datas para alertas/heatmaps |
| `/api/v1/buscar/por-local` | `POST` | Busca inteligente por cidade/estado com concorrência e produto cartesiano |
| `/api/v1/aeroportos` | `GET` | Consulta/autocomplete dos 7.835 aeroportos com `descricao_curta` e busca textual |
| `/api/v1/aeroportos/{codigo_iata}` | `GET` | Detalhes de um aeroporto por IATA (ex: `GRU`) |

---

## 🧪 4. Validação e Qualidade de Código

Para rodar a suíte de testes e o linter do projeto:

```bash
# Executar testes unitários e de integração
make test

# Executar linter (Ruff)
make lint
```

- **Resultado da Suíte de Testes**: **15 passed in 0.51s**
- **Resultado do Linter**: **All checks passed!**
