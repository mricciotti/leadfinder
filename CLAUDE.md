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
| Bairros de São Paulo numa caixa de escolha com filtro (`<datalist>`), a partir de `bairros_sp.json`: 596 nomes de `place=suburb`, `quarter` e `neighbourhood` do OpenStreetMap, baixados em 03/11/2026 com o ponto de cada um. `python places.py` baixa de novo. Outras cidades continuam com texto livre | Escolher é mais rápido que digitar e evita erro de grafia. Os nomes vêm do mapa, então existem de fato. |
| Bairro escolhido da lista busca em volta do ponto dele (caixa de cerca de 1,8 km, `MIN_HALF_SPAN`) e não chama o Nominatim. Nome fora da lista, ou outra cidade, segue pelo Nominatim como antes | O Nominatim devolvia a estação de trem para "Pinheiros" (61 lugares). Com o ponto do bairro vieram 137. Também poupa uma chamada ao serviço. |
| Overpass: até 4 tentativas, com espera de 5, 15 e 30 s, em 429, 502, 503, 504 e timeout. Erro de pedido (400, 404) não repete. O Nominatim é consultado uma vez só | O Overpass público falha de forma intermitente (502 em várias buscas reais). `search` recebe `transport` e `sleep` para testar sem rede e sem esperar. |
| Controle de funil já na fase 1 (novo, **possível prospecto**, contatado, respondeu, fechado, descartado). A etapa `prospecto` foi criada pelo Matheus na tela e implementada de verdade em 04/11/2026 | O Matheus marca à mão os leads que valem uma abordagem antes de contatar. Possível prospecto ainda é "não abordado": `db.NOT_APPROACHED = (novo, prospecto)` vale para o filtro "ainda não abordados", para "Já abordados" e para a contagem das áreas. |
| Migração 3 recria a tabela `leads` para trocar a regra `CHECK` das etapas (o SQLite não altera `CHECK`): cria `leads_new`, copia tudo, apaga `leads` e renomeia, numa transação só, com cópia do banco antes. Se o banco já aceitar `prospecto`, não faz nada. Foi a única migração não aditiva | Uma etapa nova exige mudar a regra, e a regra só muda recriando a tabela. Validada numa cópia do banco real: 63 leads idênticos em todas as colunas, histórico idêntico, integridade ok. Para adicionar outra etapa no futuro, é preciso outra migração do mesmo tipo (ajuste `OLD_STAGE_CHECK`). |
| Etapa nova precisa mudar três lugares: `db.STATUSES` (e a migração), `STAGES`, `STATUS_LABELS` e `STATUS_TONES` em `static/index.html`. Só a tela não basta: o servidor recusa a etapa | Foi o erro que quebrou a primeira tentativa. |
| Botão "Limpar filtros (n)" aparece quando há filtro ativo, e a mensagem de erro some quando uma ação dá certo | A busca aplica filtro de bairro sozinha, e o Funil o herda. Leads de outros bairros pareciam sumidos. |
| O histórico de etapas é a parte mais valiosa do funil | Mostra quantas abordagens são necessárias para fechar um cliente. |
| Pontuação por regras simples, sem IA, em `scoring.py` | Duas notas independentes (facilidade de contato e oportunidade), cada uma com nível e motivos em português, mais as ofertas (o que vender) e a prioridade. Pesos e níveis em dicionários no topo do módulo, sem arquivo de configuração. |
| Notas calculadas na leitura, nunca gravadas | Mudar um peso vale na hora para todos os leads, sem migração. |
| Prioridade alta = oportunidade alta ou máxima mais pelo menos um canal de contato (endereço não conta) | Lead sem como ser abordado não é prioridade, por melhor que seja a oportunidade. |
| `nao_verificado` e `site_informado` dão oportunidade "indeterminada", nunca baixa | Falta de dado não é prova de nada. |
| Ordenação por prioridade, depois oportunidade, depois pontos de contato, depois nome | O OpenStreetMap não tem nota nem número de avaliações, e avaliação nunca entra na pontuação. |
| IDs no formato `node-123` (hífen, não barra) | Barra quebra a rota `/api/leads/{id}`. |
| `create_app(db_path, searcher)` recebe a busca por injeção | Permite testar a API sem rede. |
| Estrutura enxuta: `overpass.py`, `contacts.py`, `scoring.py`, `filters.py`, `export.py`, `db.py`, `main.py`, `static/index.html` | Um módulo por responsabilidade real, sem pastas prematuras. |
| Checagem manual em colunas `manual_*` separadas, nunca tocadas pela reimportação. A leitura (`db.to_lead`) sobrepõe o manual ao mapa | O dado que o Matheus conferiu vale mais que o do mapa e não pode se perder numa nova busca. |
| "Sem site" confirmado é a coluna `absence_confirmed_at`, que sobrepõe o estado do site na leitura. Desfazer é apagar a data. Some se o mapa passar a informar um site | Reversível sem guardar o estado anterior. |
| Site manual só aceita site próprio. Instagram vai no campo próprio | Evita misturar rede social com site. |
| Filtros e exportação no servidor, pela mesma função (`filters.apply`). Bairro e cidade comparados sem maiúsculas e acentos | O arquivo exportado é exatamente o que está na tela. |
| Exportação vazia devolve 404 com mensagem, sem arquivo | Não gerar arquivo vazio em silêncio. |
| CSV em UTF-8 com BOM e `;`, telefone em formato nacional, células com `=`, `@`, tab, CR ou `+`/`-` que não sejam telefone recebem `'` na frente | Abrir certo no Excel pt-BR e evitar CSV Injection sem corromper telefone. |
| Histórico de etapas na tabela `status_changes`, gravado só quando a etapa muda | Base para medir quantas abordagens levam a um cliente. Ainda não aparece na tela. |
| Lugares com site **não são mais descartados**. O campo de site é classificado em próprio, rede social, página de links, delivery ou WhatsApp | Saber quem só tem Instagram ou Linktree é oportunidade, e quem tem site pode precisar de reformulação. |
| Estados do site: `nao_verificado`, `sem_site_na_fonte`, `so_rede_social`, `site_informado` (vindos da fonte) e `site_ok`, `site_com_problemas`, `site_inacessivel`, `ausencia_confirmada` (verificação futura ou ação manual) | Separar ausência de informação de ausência verificada. |
| Migração aditiva por `PRAGMA user_version`, com cópia do banco antes | Nunca perder status, anotações nem IDs. |
| Reimportar atualiza os dados do mapa. Contato ausente na fonte não apaga o já conhecido. Status, anotações e favorito nunca mudam. Lead descartado não é tocado. Estado de site verificado só volta ao da fonte se o site mudar | O mapa melhora com o tempo, mas o trabalho do Matheus é dele. |
| Deduplicação pelo ID do OSM. Fallback: mesmo nome normalizado, tipos diferentes (ponto e área) e até cerca de 50 m (`SAME_PLACE_DEGREES`). Telefone nunca é chave | O mesmo lugar às vezes aparece como ponto e como área. |
| Telefone guardado como veio e também normalizado (DDD mais número) com tipo `fixo`, `celular`, `outro` ou `invalido` | WhatsApp só pode ser "potencial", e só para celular. |
| Design da interface (redesenhada em 03/11/2026): barra lateral escura com quatro seções (Buscar, Leads, Planilha, Funil), indicadores no topo, tabela com selos coloridos, funil em colunas, painel lateral com os detalhes de cada lead, fonte Inter, índigo como cor de destaque | Seguir o padrão de ferramentas de vendas que o Matheus indicou como referência. Claro e escuro via `prefers-color-scheme`. |
| Buscar (buscar no mapa) e Leads (trabalhar a lista) são seções separadas. Buscar também lista as "áreas que você já buscou", derivadas dos leads salvos (`filters.areas`), sem tabela de buscas. Depois de salvar, o app abre Leads filtrado no que chegou | Buscar leva meio minuto e usa serviço externo, filtrar é instantâneo. Misturar as duas confundia. Limite: uma busca que não trouxe nenhum lead não aparece no histórico. Leads antigos sem cidade se juntam à área de mesmo segmento e bairro só quando existe uma única cidade possível. |
| **A busca não grava nada.** `POST /api/search` devolve uma prévia (cada lugar com avaliação, `saved`, `duplicate` e `recommended`) e a guarda na memória do servidor por `search_id` (as últimas `MAX_PREVIEWS = 10`). Só `POST /api/search/{id}/save` com os `ids` escolhidos grava. Os leads que já estavam na lista são atualizados com os dados novos do mapa, sem tocar em etapa, notas, favorito e checagem manual. O que o Matheus não salvar não existe no banco, na Planilha, no CSV nem nos `.bak` | O Matheus não quer lista inflada de lugares que nunca viu. Medido: só 22% dos leads salvos tinham algum canal de contato. A prévia fica no servidor, e não no navegador, para o cliente não poder mandar dados inventados. Limite: reiniciar o servidor (inclusive o `--reload` ao editar código) apaga as prévias, e salvar uma prévia que sumiu responde "A prévia expirou". |
| Recomendado = lugar novo, não repetido, com canal de contato (telefone, e-mail, Instagram ou outras redes; endereço não conta) e site em `sem_site_na_fonte` ou `so_rede_social`. É o que já vem marcado na prévia | Lead sem como ser abordado, ou que já tem site próprio, não é o foco inicial. O Matheus pode marcar o resto à mão: precisa de checagem manual para virar abordável. |
| Repetido na prévia: mesmo nome, outro tipo de elemento do mapa (ponto e área) e até 50 m, contra o banco **e** contra os outros lugares da mesma busca. A prévia mostra uma vez só | Achado em busca real: "Museo Verônica" vinha como ponto e como área, e as duas estavam marcadas. |
| A Planilha mostra as linhas do Leads CSV, montadas por `export.table` a partir da mesma função do arquivo (`lead_row`) | O Matheus não tem como abrir CSV. Tela e arquivo nunca divergem. A tela mostra fórmulas como texto, sem a proteção do arquivo, porque o navegador não as executa. |
| Sem nota de 0 a 100 e sem estrelas de avaliação na interface, ao contrário das referências | Não há dado que sustente essa precisão, e o OpenStreetMap não tem avaliações. Ficam os níveis com motivos. |

## Fase 5 (vitrine, mensagem e abordagem): decisões (implementada em 08/11/2026)

| Decisão | Motivo |
|---|---|
| Vitrine é HTML estático gerado por funções puras em `vitrines.py` (`slug_for`, `content_for`, `render`, `client_files`), com `templates/vitrine.html`, `.css` e `.js`. Visual editorial (títulos condensados, faixa em marquee, serviços numerados, "como funciona", avaliações, mapa, botão flutuante de WhatsApp), quatro paletas (ouro, floresta, terracota, azul) escolhidas por segmento em `SEGMENT_COPY`/`PALETTES` | O Matheus rejeitou o modelo básico e depois o neon ("cara de iniciante e de IA"). Os dois HTMLs de exemplo dele são a referência de qualidade. |
| **Conteúdo de exemplo permitido, sempre marcado "MODELO"** (serviços, textos, fotos ilustrativas com "Imagem ilustrativa"). Fato do negócio nunca é inventado: horário, avaliação, preço, anos de tradição. Avaliações = link para o Google Maps, sem números. Os campos que o Matheus preenche no painel (serviços, horário, endereço com número, categoria, cardápio, Instagram pelo campo manual) **substituem** o conteúdo MODELO | A prévia precisa impressionar sem mentir. Isto muda o PROMPT original ("campo ausente omite a seção") e foi aprovado pelo Matheus. |
| JavaScript permitido em **um único script fixo** (`templates/vitrine.js`), liberado por CSP `script-src 'sha256-…'` calculado do arquivo (`SCRIPT_HASH`). CSP: `default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src https://images.unsplash.com data:; frame-src https://www.openstreetmap.org; base-uri 'none'; form-action 'none'`. Exportação grava com `write_bytes` (quebra de linha LF) para o hash continuar válido. Editar o `.js` ou o texto do `<script>` do `.html` muda o hash: use `render`, nunca edite o HTML exportado à mão | Revelar ao rolar, menu e montador de mensagem de WhatsApp. O montador valida o número (`^\d{12,13}$`), usa `textContent` e `encodeURIComponent`, e o host é fixo `wa.me`. |
| Botão principal: WhatsApp só com `manual_whatsapp` ou celular; senão "Ligar agora"; sem telefone, "Como chegar". Segmento de comida sem cardápio cadastrado: "Peça pelo WhatsApp" | Telefone fixo não é WhatsApp. |
| Prévia: faixa "Prévia criada para {nome}", `noindex,nofollow` e rodapé "Página de demonstração". Aprovada: `<body class="approved">`, sem faixa e sem `noindex` | Evita uma prévia indexada com o nome de um negócio que não pediu. |
| Migração 4, aditiva: colunas `follow_up_at` e `do_not_contact_at` em `leads` e tabela `vitrines` (`lead_id` e `slug` únicos, `slug` com 3 a 60 caracteres no `CHECK`), com cópia do banco antes | "Não contatar" é coluna, não etapa, porque mudar o `CHECK` exige recriar a tabela. |
| Mensagens em `mensagens.py`: cinco textos (`sem_site`, `so_rede_social`, `delivery`, `site_com_problemas`, `follow_up`), até 400 caracteres, sem IA, inteligência artificial, desenvolvedor, tecnologia nem "quer um site", "em {bairro}" (nunca "no"), começam com "Meu nome é Matheus." O caso vem da oferta principal; `site_com_problemas` sem um problema real cai em `sem_site`. A mensagem do painel é editável e o texto editado não é guardado | Mostrar antes de perguntar. |
| Abordagem em `outreach.py`: dia do Brasil em UTC-3 fixo; `DAILY_LIMIT = 15` conta leads distintos que foram para `contatado` hoje (`status_changes`); fila "Para abordar hoje" = novo ou prospecto, com canal, com vitrine, sem "não contatar", cortada no que resta do limite; follow-up = `contatado` há `FOLLOW_UP_DAYS = 3` dias ou mais, sem `follow_up_at`, um por lead. O relógio é injetável (`now`) | Poucas mensagens personalizadas por dia, para o número não ser banido. |
| Abrir o WhatsApp não muda a etapa. Só "Enviei" muda para `contatado`, e "Enviei o follow-up" grava `follow_up_at` | Abrir não é enviar. |
| Exportar grava `<LEADFINDER_VITRINES_DIR>/<slug>/index.html` (padrão `vitrines_publicadas/`) e marca `exported_at`; pasta do cliente grava `<LEADFINDER_CLIENTES_DIR>/<slug>/` (padrão `clientes/`) com `dados.json` (sempre reescrito, com origem e data por campo e `campos_ausentes`) e `PROMPT.md` (só se não existir). Ambas as pastas estão no `.gitignore`, e o código confere que o destino fica dentro delas | Camada 2: páginas mais ricas feitas pelo Matheus no Claude Code a partir da pasta do cliente. |
| Link público = `LEADFINDER_VITRINE_BASE` + slug. Sem a variável, a tela avisa que o link ainda não pode ser enviado | O código não depende do provedor. |

**Riscos e itens não verificados da Fase 5**
- **Vercel Hobby proíbe uso comercial** (verificado); o plano Pro custa US$ 20/mês. Começar nele para testar é aceitável, mas prospectar de verdade exige trocar de provedor ou pagar. Termos do Cloudflare Pages não foram verificados.
- Unsplash permite uso comercial sem atribuição (verificado). **Não verificado:** hotlink em produção e entrega da foto dentro do site de um cliente. Só há fotos para beleza e pet; os outros segmentos usam hero sem foto.
- Barlow Condensed e DM Sans: SIL OFL (verificado).
- **Não verificado:** a abertura real do WhatsApp com a mensagem, o mapa embutido do OpenStreetMap em produção, a vitrine num celular de verdade (medido só no Edge headless: sem rolagem horizontal em 390 px) e o painel lateral em navegador interativo.
- Os repositórios de referência (vitrineai.app, caca-cliente, fabrica-de-sites, prospeccao, vitrineai, VitrineAI-Factory, VitrineAI-FACTORY-ENTERPRISE-X) foram lidos. Três não tinham relação com o projeto e foram descartados. Nenhum código foi copiado.

## Estado atual

- **Fase 5 implementada em 08/11/2026** (vitrine, mensagem, fila do dia, follow-up, "não contatar", pasta do cliente). **Próximo passo: a segunda pausa para prospectar (10 a 15 abordagens com prévia)** antes das Fases 6 a 9. O Matheus ainda precisa validar à mão: publicar uma pasta exportada, abrir o WhatsApp com a mensagem e ver a vitrine no celular.
- Fase 5 validada com 561 testes e 38 checagens da tela num DOM simulado (jsdom) contra o servidor real com busca falsa: criar vitrine, editar, aprovar, exportar, pasta do cliente, mensagem editável com link de WhatsApp, Copiar, "Enviei", "Enviei o follow-up", "Não contatar", filtros de fila. Limite dessa checagem: a fila "Para abordar hoje" terminou vazia no cenário, então a ordenação e o corte por limite diário estão cobertos só pelos testes de `outreach.py`.

- Evolução em fases descrita em `PROMPT-evolucao-leadfinder.md`. **Fases 2, 3 e 4 concluídas em 03/11/2026** (dados e ingestão; pontuação e ofertas; checagem manual, filtros, favoritos e CSV). **Primeira pausa para prospectar concluída em 07/11/2026:** 5 leads abordados com "quer um site?", 5 sem interesse; não havia nada concreto para mostrar. **Fase 5 concluída em 08/11/2026** (ver abaixo), seguida de uma segunda pausa para abordar 10 a 15 leads com prévia.
- **561 testes passando** (eram 348 antes da Fase 5; contatos, pontuação, filtros, exportação, consulta ao mapa, classificação de site, banco, migrações, API).
- Tela nova validada num DOM simulado (jsdom) contra o servidor real, com 54 leads reais migrados mais 4 sintéticos, em 88 checagens, incluindo a lista de bairros, a troca de cidade, a etapa Possível prospecto (com a migração do banco ao subir o servidor), o botão Limpar filtros e a prévia da busca (marcar, desmarcar, salvar, descartar, verificar que nada é gravado antes de salvar), com um buscador falso para não depender de rede: as quatro seções, o histórico de áreas, "Ver leads", "Buscar de novo", a volta para Leads depois da busca, a Planilha com as mesmas colunas e linhas do Leads CSV, o funil, o painel do lead (checagem manual, confirmar e desfazer "sem site", etapa, anotação), filtros, favoritos, exportação e busca com bairro em minúsculas.
- O visual foi conferido em capturas do Edge headless no modo escuro (Buscar, Leads, Planilha, Funil, 1440 px e 500 px). Essas capturas pegaram um erro que o jsdom não vê: regras de `display` anulavam o atributo `hidden`, hoje corrigido por `[hidden] { display: none !important }`. **Não verificado:** o painel lateral aberto, o tema claro, a largura de 390 px, a abertura do CSV no Excel pt-BR e a tela com um navegador interativo.
- A coluna `score` (completude de 0 a 6) continua sendo gravada pela ingestão, mas não é mais exibida nem usada para ordenar.
- Busca com prévia validada com dados reais em 04/11/2026 (restaurante em Moema: 38 lugares, 29 sem site no mapa, 2 recomendados; salão na Vila Mariana: 3 já na lista), numa cópia do banco: a busca não gravou nada e salvar gravou só os escolhidos.
- Busca real executada em 03/11/2026 (restaurante em Pinheiros): 61 lugares, 54 sem site na fonte, 7 com site próprio, 11 com telefone (todos fixos), nenhum com Instagram, e-mail ou WhatsApp.
- Migração validada com um banco real criado pelo código antigo: 54 leads preservados com status e anotações.
- **A reimportação real com o código novo ainda não rodou:** o Overpass respondeu 502 nas duas tentativas seguintes. Ela está coberta só por testes com dados simulados.

## Limites conhecidos (não esconda do Matheus)

- **"Sem site cadastrado" não significa "sem site".** O mapa só sabe o que alguém preencheu. A checagem manual dos melhores leads (botão "Conferir site") é obrigatória antes de abordar, porque abordar quem já tem site queima a credibilidade.
- Não existe, de graça, caminho 100% automático e confiável para saber se uma empresa tem site.
- Cobertura do OpenStreetMap no Brasil é incompleta.
- Bairros pequenos podem vir do Nominatim como ponto, sem área. O código expande a área mínima (`MIN_HALF_SPAN = 0.008` grau, cerca de 900 m), mas o resultado deve ser conferido.
- Nominatim e Overpass têm política de uso justo. Uso pessoal e moderado, com `User-Agent` identificado. Sem laços de busca em massa.
- A prévia de uma busca só existe na memória do servidor e some ao reiniciar. O histórico "Áreas que você já buscou" só mostra o que foi salvo.
- Busca de bairro grande (ou da cidade inteira) pode estourar o tempo do Overpass. Uma busca de bairro levou 26 s, e o Overpass público às vezes responde 502. Com as novas tentativas, uma busca em momento ruim pode levar alguns minutos, e se todas falharem a tela avisa para esperar um minuto.
- O Nominatim pode devolver um ponto em vez do bairro. Para "Pinheiros, São Paulo" o primeiro resultado é a estação de trem. Os bairros da lista contornam isso, mas a área buscada continua sendo uma caixa de cerca de 1,8 km em volta do ponto, não o contorno do bairro.
- A lista de bairros tem subdivisões pequenas ("Jardim X", conjuntos habitacionais, COHAB) e não distingue dois bairros com o mesmo nome em pontos diferentes: fica o de maior categoria. "Brooklin" aparece só como "Brooklin Novo" e "Brooklin Velho". A lista é uma foto de 03/11/2026.
- Alguns endereços do mapa trazem a cidade sem acento ("Sao Paulo"). Filtros e histórico tratam as duas grafias como a mesma.
- A UF vem de `addr:state` quando existe (quase nunca no Brasil) e, senão, do `ISO3166-2-lvl4` do Nominatim. A cidade vem de `addr:city` e, senão, da busca.
- Leads gravados antes da migração ficam `nao_verificado` e sem cidade nem UF até serem reimportados.
- Site com valor inválido no mapa é tratado como `sem_site_na_fonte`.

## Fora do escopo por enquanto

Só entra depois da segunda pausa (10 a 15 abordagens com prévia), e cada item passa pelo tribunal antes de começar:

1. Importação dos dados abertos do CNPJ (Receita Federal) filtrando por CNAE, município e data de abertura: Fase 8 do prompt.
2. Checagem automática de site com prova local e enriquecimento: Fase 6 do prompt. PageSpeed fica de fora por enquanto.
3. Busca por cidade inteira para segmentos esparsos e captação em várias cidades: Fase 7 do prompt.
4. Planilha Excel (XLSX) com aba de resumo: Fase 9 do prompt.
5. Geração da mensagem de abordagem com a API da Anthropic (tem custo). Na Fase 5 a mensagem sai de modelos fixos, e a personalização da vitrine com IA é feita pelo Matheus no Claude Code.
6. Envio automático de mensagens e integração com WhatsApp não oficial: proibidos, não estão em avaliação.

## Segmentos novos (adicionados em 04/11/2026, medidos no OpenStreetMap em 03/11/2026)

Contagem de negócios com nome numa caixa que cobre São Paulo e um pouco dos vizinhos (inclui redes e franquias, e "sem site" quer dizer sem site cadastrado no mapa). Telefone no mapa: 20% a 50% conforme o segmento.

| Segmento (tags) | Negócios | Sem site no mapa |
|---|---|---|
| Clínicas e consultórios (`amenity=doctors`, `clinic`, `healthcare=doctor`, `clinic`) | 763 | 88% |
| Oficina mecânica (`shop=car_repair`) | 751 | 92% |
| Pet shop e banho e tosa (`shop=pet`, `pet_grooming`) | 365 | 90% |
| Confeitaria e doceria (`shop=pastry`, `confectionery`) | 207 | 90% |
| Sorveteria (`amenity=ice_cream`) | 216 | 89% |
| Ótica (`shop=optician`) | 245 | 94% |
| Veterinário (`amenity=veterinary`) | 178 | 79% |
| Imobiliária (`office=estate_agent`) | 148 | 85% |
| Autoescola (`amenity=driving_school`) | 88 | 93% |
| Escola de idiomas (`amenity=language_school`) | 118 | 75% |

Os oito primeiros da tabela (clínica, oficina, pet shop, ótica, confeitaria, sorveteria, veterinário e imobiliária) estão em `SEGMENTS` no `overpass.py`. Para adicionar outro, inclua uma linha com o rótulo e as tags. Confeitaria e sorveteria estão em `FOOD_SEGMENTS`, então ganham a oferta de cardápio digital. Autoescola e escola de idiomas ficaram de fora por enquanto. `amenity=clinic` pode incluir dentistas, que também têm segmento próprio.

**Achado das buscas reais (04/11/2026):** numa caixa de um bairro, os segmentos novos rendem pouco: oficina na Mooca 0 lugares, confeitaria na Moema 2, clínica na Vila Mariana 3. As contagens da tabela são da cidade inteira. Restaurante é denso (137 em Pinheiros), os outros não. Para esses segmentos a área de busca precisa ser maior, e isso ainda não foi decidido.

Ficam de fora: `shop=barber` (0 resultados; as barbearias já entram em `shop=hairdresser`), fisioterapia, psicologia, eletricista, encanador e chaveiro (o OpenStreetMap quase não os mapeia, de 2 a 30 por tipo). Segmentos de comida novos precisam entrar em `FOOD_SEGMENTS` no `scoring.py` para ganhar a oferta de cardápio digital.

## Regra de ouro do negócio

O gargalo do side hustle é **fechar clientes, não achar leads**. Uma ferramenta perfeita sem mensagens enviadas é procrastinação bem organizada.

- O Matheus deve prospectar em paralelo, com os primeiros leads e um mockup para 3 a 5 deles.
- **Mostrar antes de perguntar.** A abordagem leva uma prévia com o nome do negócio e termina com um pedido pequeno ("dá uma olhada"). "Quer um site?" sem nada para ver rendeu 5 "não" em 5.
- Se em duas semanas não houver conversas, o problema não é a ferramenta. Diga isso.
- Mensagem curta, específica ao negócio, focada no resultado ("seus clientes acham o cardápio e chamam no WhatsApp"), sem falar de IA ou tecnologia.
- Nada de disparo em massa no WhatsApp, porque o número é banido. Poucas mensagens personalizadas por dia.
- **LGPD:** só dados de contato empresarial, e parar de contatar quem pedir.
- Pacote que vende melhor que "um site": landing page, Google Business Profile, botão de WhatsApp e cardápio com QR code.

## Como rodar

```
python -m venv .venv
.venv\Scripts\Activate.ps1          (Windows; no Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m pytest
python -m uvicorn main:app
```

A interface fica em `http://localhost:8000`. O banco é o `leads.db`, na pasta do projeto (variável `LEADFINDER_DB` muda o caminho).

## Mapa do código

- `overpass.py`: segmentos (`SEGMENTS`), geocodificação no Nominatim (área e UF), consulta ao Overpass, `parse_places` (todos os lugares com nome, com `presence` classificando site e redes) e pontuação. A função `search` devolve `{"total": n, "leads": [...]}`.
- `places.py`: `names(city)` e `find(bairro, cidade)` leem `bairros_sp.json` (só São Paulo). `from_overpass` transforma a resposta do mapa na lista, `save` grava e `refresh` baixa tudo (`python places.py`).
- `contacts.py`: funções puras e listas configuráveis. `normalize_phone`, `normalize_uf`, `normalize_url` (só http e https, sem credenciais, sem parâmetros de rastreamento em `TRACKING_PARAMS`), `classify_url` (domínios em `URL_KINDS`), `is_free_site` (`FREE_SITE_HOSTS`) e `email_kind` (próprio ou genérico, por `GENERIC_EMAIL_DOMAINS`; e-mail inválido só na Fase 6).
- `scoring.py`: `evaluate(lead)` devolve `contact`, `opportunity`, `offers` e `priority`. `ranked(leads)` anexa a avaliação em `evaluation` e ordena. Para adicionar uma oferta, inclua-a em `OFFERS` e a regra em `offer_keys`.
- `filters.py`: `apply(leads, wanted)` (uma regra por filtro, em `matches`), `SITE_FILTERS` e `options` (valores distintos para os menus).
- `export.py`: `leads_csv` (colunas comerciais em português), `full_csv` (todas as colunas mais a avaliação), `csv_safe` e `file_name`.
- `db.py`: tabela `leads` com `status` e `site_state` validados por `CHECK`. `connect` aplica `MIGRATIONS` conforme o `user_version`, com backup antes. `add_leads` faz upsert (veja as decisões) e devolve quantos são novos. `update_lead(conn, id, **campos)` aceita só os campos de `EDITABLE` mais `absence_confirmed`, data a checagem manual e grava o histórico. `to_lead` monta a visão efetiva (manual por cima do mapa). `other_links` é uma lista guardada em JSON.
- `main.py`: rotas `GET /`, `GET /api/segments`, `GET /api/leads` (filtros por query, ordenado, cada lead com `evaluation`), `GET /api/filter-options`, `GET /api/neighborhoods?city=` (nomes para a caixa de escolha), `GET /api/areas` (áreas já buscadas), `GET /api/leads-table` (colunas, ids e linhas do Leads CSV, para a Planilha), `GET /api/export/leads` e `GET /api/export/completo` (mesmos filtros mais `status`), `POST /api/search` (devolve a prévia: `search_id`, `total`, `found`, `new`, `known`, `duplicates`, `without_site`, `recommended` e `leads`; não grava), `POST /api/search/{search_id}/save` (corpo `{"ids": [...]}`; devolve `added` e `refreshed`), `PATCH /api/leads/{id}` (etapa, anotação, favorito, campos `manual_*`, `absence_confirmed`; devolve o lead com `evaluation`).
- `static/index.html`: página única em HTML, CSS e JS puros, sem build e sem dependências além da fonte Inter do Google Fonts (com alternativa do sistema). Quatro seções (`#buscar`, `#leads`, `#planilha`, `#funil`) e um painel lateral por lead. O estado fica no objeto `state` e tudo é redesenhado por `render()`. Os selos usam os mapas `*_LABELS` e `*_TONES` no topo do script.
- `vitrines.py`: `slugify`, `slug_for`, `content_for(lead, overrides)`, `render(content, preview, year=None)`, `client_files`, `SEGMENT_COPY`, `PALETTES`, `PHOTOS`, `SCRIPT`, `SCRIPT_HASH`, `CSP`. Usa `templates/vitrine.html`, `vitrine.css` e `vitrine.js`.
- `mensagens.py`: `MESSAGES`, `FORBIDDEN`, `MAX_LENGTH`, `case_for`, `problems_with`, `build`.
- `outreach.py`: `DAILY_LIMIT`, `FOLLOW_UP_DAYS`, `sent_today`, `today`, `daily_queue`, `follow_up_due`, `follow_ups`.
- Rotas da Fase 5 em `main.py`: `GET /api/today`, `POST /api/leads/{id}/vitrine`, `GET` e `PATCH /api/vitrines/{slug}`, `GET /s/{slug}`, `POST /api/vitrines/{slug}/export`, `POST /api/vitrines/{slug}/folder`, `GET /api/leads/{id}/message?kind=abordagem|follow_up`. `GET /api/leads` aceita `queue=hoje|follow_up`; `PATCH /api/leads/{id}` aceita `do_not_contact` e `follow_up_sent`. Variáveis: `LEADFINDER_VITRINES_DIR`, `LEADFINDER_CLIENTES_DIR`, `LEADFINDER_VITRINE_BASE`. `db.py` ganhou `vitrines`, `contacted_at` (subconsulta em `status_changes`) e as funções `create_vitrine`, `update_vitrine`, `vitrine_by_slug`, `mark_exported`.
- `tests/`: um arquivo de teste por módulo.

## Primeira tarefa sugerida no Claude Code

1. Rodar `python -m pytest` e confirmar que os 561 testes passam.
2. Subir o servidor e fazer a primeira busca real (por exemplo, restaurante em Pinheiros).
3. Se algo falhar, corrigir com teste que reproduz o erro antes da correção.
4. Antes de qualquer funcionalidade nova, perguntar ao Matheus como foi a checagem manual dos primeiros leads.


# repositorios para ter de base
abra o claude no chrome (chromium) acesse os repositorios e leia os codigos, se nao conseguir ou nao tiver acesso para ler, me avise( nao invete)
https://www.vitrineai.app/
https://github.com/rafaelcaetite/caca-cliente
https://github.com/hectorautomacoesdev/fabrica-de-sites
https://github.com/VictorHugodaSilvaSousa/prospeccao
https://github.com/guiviqunha/vitrineai
https://github.com/cschibelsky-star/VitrineAI-Factory
https://github.com/cschibelsky-star/VitrineAI-FACTORY-ENTERPRISE-X