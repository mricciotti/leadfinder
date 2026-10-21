# Leadfinder: contexto e modo de trabalho

Este arquivo resume a conversa que originou o projeto. Leia inteiro antes de qualquer tarefa. Ele vale mais do que seus hábitos padrão.

## Quem é o Matheus e por que este projeto existe

- Dev front-end com experiência em integração com back-end. Domina TypeScript e React. **Python é aprendizado**, então explique o que fizer e prefira código legível a código esperto.
- Quer abrir um side hustle de desenvolvimento freelance, começando por **sites e landing pages para pequenos negócios locais de São Paulo** (restaurantes sem cardápio online, por exemplo).
- O projeto é uma **ferramenta pessoal de prospecção** que encontra negócios sem site e controla o funil de contato.
- Objetivos, nesta ordem: (1) fechar clientes de verdade, (2) aprender no processo.
- **Orçamento zero** por enquanto. Nada de API paga nem cartão cadastrado.

## Modo de trabalho (a parte mais importante)

O Matheus pediu explicitamente um parceiro que **não concorda com tudo**. Isso vale para as ideias dele e para as suas.

1. **Não aceite decisões de cara.** Se a ideia for ruim, diga antes de escrever código, com o motivo e uma alternativa. Formato: "Discordo porque X. Alternativa: Y. Trade-off: Z."
2. **Antes de uma decisão não trivial, faça o "tribunal":** confronte a proposta sob estes ângulos e só então responda.
   - Simplicidade: dá para fazer com menos?
   - Custo: continua gratuito?
   - Risco: termos de uso das fontes, LGPD, segurança.
   - Manutenção: o Matheus entende e consegue mexer sozinho?
   - Objetivo: isso ajuda a fechar clientes ou é procrastinação organizada?
   - Aprendizado: ele aprende algo ou só recebe pronto?
3. **Dê ideias e sugira sem esperar o pedido**, mas separe o que foi pedido do que é sugestão. Sugestão não implementada não vira código.
4. **Apresente alternativas com trade-offs e recomende uma.** Espere o Matheus escolher antes de seguir.
5. **Defina arquitetura antes de codar.** Mudança de arquitetura é discutida, não feita no meio de uma tarefa.
6. **Não invente.** Preço de API, limite, termo de uso e comportamento de ferramenta externa são verificados, e o que não foi verificado é dito como não verificado.
7. **Diga o que não conseguiu testar.** Se algo depende de rede ou de serviço externo, explique como validar.
8. **Se não souber o que ele quer, pergunte uma coisa por vez**, depois de ter tentado resolver sozinho.

Nota sobre o "tribunal": o Matheus viu uma skill com esse comportamento (consultar vários pontos de vista antes de responder), mas **não foi identificada**. O repositório `multica-ai/andrej-karpathy-skills` foi avaliado e **não é essa skill**: são quatro princípios (pensar antes de codar, simplicidade, mudanças cirúrgicas, execução guiada por critério verificável). Os pontos 1 e 4 desses princípios foram adotados. Se o Matheus encontrar a skill original, avalie e proponha adotar.

## Regras de código

- **Entregue arquivos completos**, nunca trechos ou diffs parciais.
- **Sem comentários no código.** Nomes claros fazem o trabalho.
- **Siga os padrões que já existem no repositório** em vez de inventar novos.
- **Simplicidade primeiro:** o mínimo que resolve. Sem abstração para uso único, sem configuração que ninguém pediu, sem tratamento de erro para cenário impossível. Se 200 linhas podem ser 50, reescreva.
- **Mudanças cirúrgicas:** toda linha alterada deve ter relação direta com o pedido. Código morto que já existia você menciona, não apaga.
- **Guiado por critério verificável:** escreva o teste antes ou junto, e termine mostrando que passou. Para tarefa de vários passos, declare o plano com a verificação de cada passo.
- Dependências poucas: hoje são `fastapi`, `uvicorn`, `httpx` e `pytest`. Qualquer adição precisa de justificativa.

## Decisões já tomadas (e por quê)

| Decisão | Motivo |
|---|---|
| Python com FastAPI e SQLite | Fase 2 vai processar dados grandes do CNPJ, e o Matheus quer aprender Python. Sem servidor de banco. |
| Interface web em HTML puro, sem React | Uma tela só. O aprendizado desejado é em Python, e um build seria peso sem ganho. |
| Interface em vez de CSV | O Matheus não quer olhar linhas pequenas numa planilha. Cada lead é uma linha com ações e anotação. |
| OpenStreetMap (Nominatim + Overpass) como fonte | Gratuito e sem chave. Google Places foi descartado por cobrança e cartão. |
| **Sem scraping do Google Maps** | Viola os termos de uso do Google. |
| **Sem usar o REA para copiar plataformas pagas** (Speedio, Econodata) | O REA é para analisar software próprio ou autorizado. Copiar APIs privadas viola termos e é desnecessário, porque os dados vêm de fontes públicas. |
| Controle de funil já na fase 1 (novo, contatado, respondeu, fechado, descartado) | É a parte mais valiosa: mostra quantas abordagens são necessárias para fechar um cliente. |
| Pontuação por regras simples, sem IA | Telefone 3, horário 1, endereço 1, Instagram 1 (máximo 6). Constantes no código, sem arquivo de configuração. |
| Ordenação por completude do cadastro | O OpenStreetMap não tem nota nem número de avaliações. |
| IDs no formato `node-123` (hífen, não barra) | Barra quebra a rota `/api/leads/{id}`. |
| `create_app(db_path, searcher)` recebe a busca por injeção | Permite testar a API sem rede. |
| Estrutura enxuta: `overpass.py`, `db.py`, `main.py`, `static/index.html` | Um módulo por responsabilidade real, sem pastas prematuras. |
| Design da interface: lista em linhas, faixa do funil no topo, azul de placa sobre fundo frio, uma família tipográfica (Bricolage Grotesque) | Evitar o visual genérico de cartões idênticos. Claro e escuro via `prefers-color-scheme`. |

## Estado atual

- Projeto funcional, entregue em `leadfinder/` com 13 arquivos.
- **37 testes passando** (consulta ao mapa, filtro de site, pontuação, banco, API).
- Tela validada num DOM simulado (jsdom) com 24 checagens: etapas, contagens, links, WhatsApp só para celular, salvar anotação sem perder o foco, troca de status.
- Servidor sobe e responde. A busca real falha de forma limpa quando não há rede.
- **A busca real contra o OpenStreetMap ainda não foi executada.** O ambiente onde o código foi escrito não alcança esses serviços. A primeira execução real é na máquina do Matheus, e qualquer erro dela é o próximo ponto a corrigir.

## Limites conhecidos (não esconda do Matheus)

- **"Sem site cadastrado" não significa "sem site".** O mapa só sabe o que alguém preencheu. A checagem manual dos melhores leads (botão "Conferir site") é obrigatória antes de abordar, porque abordar quem já tem site queima a credibilidade.
- Não existe, de graça, caminho 100% automático e confiável para saber se uma empresa tem site.
- Cobertura do OpenStreetMap no Brasil é incompleta.
- Bairros pequenos podem vir do Nominatim como ponto, sem área. O código expande a área mínima (`MIN_HALF_SPAN = 0.008` grau, cerca de 900 m), mas o resultado deve ser conferido.
- Nominatim e Overpass têm política de uso justo. Uso pessoal e moderado, com `User-Agent` identificado. Sem laços de busca em massa.
- Busca de bairro grande (ou da cidade inteira) pode estourar o tempo do Overpass.

## Fora do escopo por enquanto

Só entra depois que o Matheus tiver abordado leads reais, e cada item passa pelo tribunal antes de começar:

1. Importação dos dados abertos do CNPJ (Receita Federal) filtrando por CNAE, município e data de abertura, para achar empresas recém-abertas, que ainda não têm site. O dump é grande, então importar só os CNAEs e municípios de interesse.
2. Checagem automática de site e PageSpeed (gratuita) para leads que têm site ruim.
3. Geração da mensagem de abordagem personalizada com a API da Anthropic (tem custo, então decidir com o Matheus).
4. Filtro por bairro e segmento na lista da interface.

## Regra de ouro do negócio

O gargalo do side hustle é **fechar clientes, não achar leads**. Uma ferramenta perfeita sem mensagens enviadas é procrastinação bem organizada.

- O Matheus deve prospectar em paralelo, com os primeiros leads e um mockup para 3 a 5 deles.
- Se em duas semanas não houver conversas, o problema não é a ferramenta. Diga isso.
- Mensagem curta, específica ao negócio, focada no resultado ("seus clientes acham o cardápio e chamam no WhatsApp"), sem falar de IA ou tecnologia.
- Nada de disparo em massa no WhatsApp, porque o número é banido. Poucas mensagens personalizadas por dia.
- **LGPD:** só dados de contato empresarial, e parar de contatar quem pedir.
- Pacote que vende melhor que "um site": landing page, Google Business Profile, botão de WhatsApp e cardápio com QR code.

## Como rodar

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
python -m uvicorn main:app
```

A interface fica em `http://localhost:8000`. O banco é o `leads.db`, na pasta do projeto (variável `LEADFINDER_DB` muda o caminho).

## Mapa do código

- `overpass.py`: segmentos (`SEGMENTS`), geocodificação no Nominatim, consulta ao Overpass, `parse_places` (descarta quem tem `website`, `contact:website`, `url` ou `contact:url`) e pontuação. A função `search` devolve `{"total": n, "leads": [...]}`.
- `db.py`: tabela `leads` com `status` validado por `CHECK`. `add_leads` usa `INSERT OR IGNORE`, então rebuscar nunca apaga status nem anotações.
- `main.py`: rotas `GET /`, `GET /api/segments`, `GET /api/leads`, `POST /api/search`, `PATCH /api/leads/{id}`.
- `static/index.html`: tela única, sem dependências além da fonte do Google Fonts (com alternativa do sistema).
- `tests/`: um arquivo de teste por módulo.

## Primeira tarefa sugerida no Claude Code

1. Rodar `python -m pytest` e confirmar que os 37 testes passam.
2. Subir o servidor e fazer a primeira busca real (por exemplo, restaurante em Pinheiros).
3. Se algo falhar, corrigir com teste que reproduz o erro antes da correção.
4. Antes de qualquer funcionalidade nova, perguntar ao Matheus como foi a checagem manual dos primeiros leads.
