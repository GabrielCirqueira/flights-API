# 🏗️ Arquitetura do Microsserviço de Voos

## 1. Visão Geral da Arquitetura

O `voobarato-flights-api` atua como uma ponte de alta performance entre a aplicação principal (Symfony / PHP) e a infraestrutura interna do Google Flights.

```mermaid
graph TD
    Client[Symfony Backend / Consumers] -->|HTTP POST + X-Internal-Token| FastAPI[FastAPI App / app/main.py]
    FastAPI --> Middleware[Middleware verificar_token_interno]
    Middleware --> Routers[Routers / app/routers/buscar.py]
    Routers --> Schemas[Pydantic Validation / app/schemas/]
    Routers --> Service[Fli Service / app/services/servico_fli.py]
    Service -->|Engine RPC + TLS Fingerprint| GoogleFlights[Google Flights RPC Internal API]
```

## 2. Decisões de Design

### Substituto do Web Scraping (`fast-flights` -> `fli`)
O mecanismo anterior baseava-se em navegar em instâncias do Chromium ou ler HTML estático. Isso apresentava diversos gargalos:
- **Fragilidade Layout/DOM**: Qualquer alteração em classes CSS do Google Flights quebrava os scrapers.
- **Alto Custo de CPU e RAM**: Instâncias de navegadores headless consomem recursos significativos.
- **Campos Incompletos**: Dados como modelo da aeronave, bagagens incluídas e conexões eram difíceis de extrair confiavelmente do HTML.

O pacote `fli` se comunica diretamente com o endpoint RPC interno do Google Flights via cliente de rede `curl_cffi`, simulando o fingerprint TLS de navegadores reais (evitando captchas e bloqueios de IP).

### Padrão de Projeto no Service Layer
Todo o código relacionado à especificação da biblioteca `fli` fica estritamente isolado em `app/services/servico_fli.py`. A aplicação FastAPI interage apenas com DTOs Pydantic limpos em português. Caso no futuro o Google Flights altere seu contrato RPC ou outra API seja adotada, apenas a camada do `servico_fli.py` precisará de modificação.

## 3. Estratégia de Resolução do Bug de Janela vs Data Exata

O bug histórico ("Preço da oferta R$303 exibido em dia cuja passagem custava R$3.853") ocorria porque o scraper antigo retornava o menor preço encontrado em uma busca por intervalo de datas sem vincular a qual dia específico aquele valor pertencia.

No novo modelo:
1. `/api/v1/buscar/janela` é usada para mapear o calendário de preços.
2. Cada item em `por_data` vincula estritamente `data` e `preco`.
3. As datas mais baratas são opcionalmente expandidas via `expandir_top`, gerando objetos `OfertaVooSaida` completos com percursos, horários e companhia aérea responsável.
