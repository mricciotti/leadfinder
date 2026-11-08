# Leadfinder: evolução para inteligência comercial local (prompt em fases)

## Como trabalhar neste prompt

- Leia o `CLAUDE.md` inteiro antes de qualquer coisa. Ele prevalece sobre este texto, exceto onde este prompt o atualiza de forma explícita.
- Execute **uma fase por vez**. Ao terminar, entregue o relatório da fase (o que mudou, arquivos tocados, saída dos testes, decisões tomadas, riscos, pendências) e **pare**. Só comece a próxima quando eu escrever "seguir".
- Discorde quando uma ideia, minha ou sua, for ruim: diga o motivo e proponha uma alternativa com trade-offs. Decisões não triviais passam pelo "tribunal" do `CLAUDE.md`.
- Nada de commit, push, PR, merge ou deploy sem minha autorização explícita. Publicar uma vitrine também é deploy: a ferramenta só gera os arquivos, quem publica sou eu.
- Código: arquivos completos, sem comentários, padrões que já existem, mudanças cirúrgicas, simplicidade primeiro, testes junto com o código. Nenhuma dependência nova sem justificativa. A única prevista é `openpyxl`, na fase 9.
- Não declare que algo funciona sem executar. O que depende de rede externa (Overpass, Nominatim, sites de terceiros, hospedagem) e não puder ser validado aqui, teste com dados simulados e me diga como validar na minha máquina.
- Documentação: cada fase atualiza o README e o `CLAUDE.md` apenas no que mudou. Fonte única de verdade. Não crie `AGENTS.md` nem arquivos duplicados.
- Se encontrar um bloqueio técnico, resolva da forma mais simples e segura. Se a solução alterar o escopo, pergunte antes.

## Objetivo

Encontrar negócios locais que precisam de **site, landing page, página de apresentação ou cardápio digital**, para eu fazer e vender. A ferramenta descobre, verifica a presença digital, diz **o que oferecer** a cada lead com justificativa, **monta uma prévia concreta para mostrar ao dono**, prepara a mensagem de abordagem individual e organiza a prospecção. Continua em Python, FastAPI, SQLite e HTML puro, com OpenStreetMap, Overpass e Nominatim, custo zero e uso pessoal.

## O que os dados reais mostraram

**03/11/2026.** Busca real de restaurantes em Pinheiros: 61 lugares, 54 sem site na fonte, 7 com site próprio (nenhum era rede social), 11 com telefone (todos fixos), **nenhum** com Instagram, e-mail ou WhatsApp. O Overpass levou 26 s por busca e respondeu 502 em 2 de 5 chamadas. O Nominatim devolveu a estação de trem de Pinheiros em vez do bairro. Consequência: o gargalo é **conseguir contato**, não verificar site.

**04/11/2026.** Numa caixa de bairro, os segmentos esparsos rendem quase nada (oficina na Mooca 0, confeitaria na Moema 2, clínica na Vila Mariana 3). Restaurante é denso, os outros não.

**Primeira pausa para prospectar (até 07/11/2026).** Abordei 5 leads perguntando se queriam um site. Os 5 disseram que não tinham interesse. Conclusão: a pergunta era abstrata e não havia nada concreto para mostrar. Dizer "não" a "quer um site?" custa zero. A próxima rodada de abordagens **mostra antes de perguntar**: uma prévia com o nome do negócio e um pedido pequeno ("posso te mandar o link?" ou "dá uma olhada"). Por isso a Fase 5 passou a ser a vitrine, antes de qualquer melhoria de descoberta.

## Estado conhecido (após a Fase 4, confira antes de cada fase)

- `overpass.py`: segmentos em `SEGMENTS`, geocodificação no Nominatim, consulta ao Overpass com até 4 tentativas, `parse_places` com `presence` classificando site e redes.
- `places.py`: bairros de São Paulo em `bairros_sp.json`; bairro da lista busca numa caixa de cerca de 1,8 km em volta do ponto.
- `contacts.py`, `scoring.py`, `filters.py`, `export.py`: normalização, notas e ofertas calculadas na leitura, filtros no servidor, Leads CSV e CSV completo.
- `db.py`: migrações por `PRAGMA user_version` com backup, `MIGRATIONS = (add_presence_columns, add_manual_check, allow_prospect_stage)`, etapas em `STATUSES` com `CHECK`, histórico em `status_changes`, checagem manual em colunas `manual_*`.
- `main.py`: busca com prévia em memória (`POST /api/search` e `POST /api/search/{id}/save`), leads, filtros, áreas, Planilha e exportações.
- `static/index.html`: quatro seções (Buscar, Leads, Planilha, Funil) e painel lateral por lead. O botão de WhatsApp abre `wa.me` **sem texto**.
- 348 testes. Não existem: vitrine, mensagem de abordagem, "não contatar", follow-up, verificação automática de site, busca por cidade inteira, CNPJ.

## Decisões já tomadas

- Notas e motivos são **calculados na leitura** por uma função pura, sem colunas no banco.
- Histórico de etapas em tabela própria (feito na Fase 4).
- "Não contatar" será coluna, não etapa (o `CHECK` não muda sem recriar a tabela). Entra na Fase 5.
- Estado de execução de buscas em lote e de verificações fica no navegador (laço que chama a API uma vez por item), não em fila no servidor.
- **Mostrar antes de perguntar:** a abordagem leva uma prévia pronta do negócio. Nada de "quer um site?" sem nada para ver.
- **A vitrine é gerada, nunca publicada pela ferramenta.** O leadfinder grava os arquivos estáticos numa pasta; eu publico.
- **Etapas do funil não mudam nesta rodada.** "Prévia enviada" é `contatado` com vitrine; não vale uma migração que recria a tabela.
- **Hospedagem (verificado em 07/11/2026):**
  - Vercel Hobby é proibido para isso: os termos dizem que só vale para uso pessoal não comercial e citam "receber pagamento para criar, atualizar ou hospedar o site" como uso comercial.
  - GitHub Pages diz que não pode ser usado como hospedagem gratuita para tocar um negócio online. Site institucional é zona cinzenta.
  - Cloudflare Pages Free: não achei proibição nas páginas de limites e de planos, mas o plano é descrito como "pessoal ou hobby" e os Termos de Uso completos não foram lidos. **Não verificado.**
  - Decisão: as **prévias** ficam num único projeto meu, de hospedagem estática escolhida por mim (a base da URL vem de variável de ambiente). O **site final** de cliente pagante fica em conta e domínio **no nome do cliente**, e eu cobro a criação e a manutenção. A ferramenta não depende de nenhum provedor.

## Restrições permanentes (valem em todas as fases)

**Fontes e limites**
- Não incorporar o scraper do Google Maps, proxies, troca de user agent para driblar limites, bypass de CAPTCHA, Cloudflare ou antibot.
- Não usar Google Places, Serper.dev ou qualquer intermediário que raspe o Google, nem Apify ou scraper de Instagram.
- Não decodificar proteções de e-mail de sites (inclui `data-cfemail` do Cloudflare). Se o site bloquear ou ofuscar, registre "bloqueado" ou "sem e-mail encontrado" e siga em frente.
- **Não criar nenhum disparo automático de mensagens**, nem integração com WhatsApp não oficial (Evolution API, Baileys e similares). O que é permitido: link `wa.me` com o texto preenchido, que eu abro e envio à mão, um lead por vez.
- Nominatim e Overpass: `User-Agent` identificado, cache de geocodificação, no máximo 1 requisição por segundo ao Nominatim, execução sequencial, teto de combinações por execução e recuo exponencial em 429, 502 e 504.
- Não usar API paga nem IA onde regra determinística resolve. A personalização da vitrine com IA é feita por mim no Claude Code, fora da ferramenta.

**Dados**
- **Ausência de campo não é ausência de site.** Toda informação comercial guarda a origem (`osm`, `manual`, `site` ou `cnpj`) e a data da coleta ou verificação.
- Nunca inventar dado. O OpenStreetMap não tem nota nem número de avaliações: não crie colunas fingindo esse dado, e avaliação nunca entra na pontuação. **A vitrine também não inventa:** nada de preço, depoimento, nota, horário, número de clientes ou "há X anos" que eu não tenha registrado.
- LGPD: minimização. Priorize contatos empresariais, registre a origem, e lead descartado ou marcado como "não contatar" não volta em novas buscas, não entra na fila do dia e não tem vitrine publicada.
- Migrações só aditivas, com backup do `leads.db` antes.

**Requisições a sites de terceiros (módulo único e guardado, Fase 6)**
- Apenas `http` e `https`, portas 80 e 443, sem credenciais na URL.
- Resolver o DNS e bloquear IPs privados, loopback, link-local, reservados, multicast e o endereço de metadados da nuvem, incluindo IPv6, IPv4 mapeado em IPv6, 6to4 e NAT64.
- **Conferir também o IP do par no momento da conexão do socket**, o que fecha o DNS rebinding.
- Revalidar a cada redirecionamento (máximo 3). Timeout curto e prazo total por site, limite de bytes por resposta, apenas conteúdo HTML, respeitar `robots.txt`, no máximo 4 tentativas por lead e 4 páginas por site.
- Toda nova tentativa (esquema, `www`, domínio provável) passa pelo mesmo fetch guardado.

**Segurança geral**
- Proteção contra CSV Injection (células iniciadas por `=`, `+`, `-`, `@`, tab ou CR). O guard não pode corromper telefones que começam com `+`: exporte o telefone em formato nacional ou isente colunas validadas por padrão.
- SQL sempre parametrizado, entradas validadas, falha de fonte externa nunca derruba a aplicação nem esconde o lead, e logs sem dados pessoais.
- HTML gerado para terceiros (vitrine) com todo texto escapado, links montados pelo código e nunca copiados de campo livre, sem JavaScript e com CSP restritiva.

## Referência analisada (`Mahanaicoach/google-maps-scraper-kit`, lida em 03/11/2026)

Licença MIT. Adaptar as ideias, não copiar código, e dar crédito no README. O motor de coleta dele (scraping do Maps com troca de user agent e rotação de proxies) é proibido aqui.

| Ideia | Origem | Decisão |
|---|---|---|
| Leads CSV com campos comerciais e redes sociais, nome de arquivo derivado da busca, filtro de e-mail aplicado também na exportação | #63 | **Adotada** (fase 4) |
| Regras de e-mail inválido em uma única fonte: no-reply, placeholders, tokens hexadecimais de 16 ou mais caracteres, `.gov` e `.mil`, fornecedores de marketing, nomes de arquivo como `logo@2x.png` | #63 | **Adotar** (fase 6) |
| Guard de fórmula que não corrompe telefone | master | **Adotada** (fase 4) |
| Retirar também `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`, sem recodificar a query quando nada sai. Reconhecer `fb.me`, `instagr.am`, `lnkd.in` | master, #64 | **Adotada** (fase 3, ajuste) |
| Fetch guardado com checagem do par no socket, prazo total e leitura limitada, só biblioteca padrão | master | **Adotar** (fase 6) |
| Outro esquema e `www`, sempre pelo fetch guardado. Seguir até achar e-mail do domínio próprio | #64 | **Adotar** (fase 6) |
| Redes sociais por expressão regular, ignorando links de compartilhar e perfis de plataformas (Wix, Shopify, iFood) | master | **Adotar** (fase 6) |
| Páginas de contato pelo texto do link, em português, incluindo "cardápio" | #64 | **Adotar** (fase 6) |
| Tag `viewport` como heurística de mobile | master | **Adotar** (fase 6) |
| Decodificar e-mail protegido pelo Cloudflare | #64 | **Descartar** |
| Pixels de anúncio, `intent_score`, verificação MX | master | **Descartar** (servem a quem já tem site e usam avaliações) |
| Divisão do mapa em grade, proxies, Docker | #46, master | **Descartar** |
| Documentação para mecanismos de IA, tabela comparativa | #36, #62 | **Descartar** |

## Referências analisadas em 07/11/2026 (VitrineAI e três repositórios parecidos)

O VitrineAI (`vitrineai.app`, pago, código fechado) acha negócios sem site, gera uma página de demonstração por nicho e deixa a mensagem pronta no WhatsApp para o usuário enviar. Hospeda tudo num único app Next.js na Vercel, com as páginas em `/s/<slug>`. Os três repositórios abaixo fazem algo parecido e **não têm licença**: só as ideias podem ser aproveitadas, com código escrito do zero e crédito no README.

| Ideia | Origem | Decisão |
|---|---|---|
| Vitrine estática gerada de dados estruturados, um modelo por nicho, só HTML e CSS, texto escapado, CSP que bloqueia recursos externos | `VictorHugodaSilvaSousa/prospeccao` | **Adotar** (fase 5) |
| Faixa de PRÉVIA e `noindex` enquanto o dono não aprova | prospeccao | **Adotar** (fase 5) |
| Mensagem por caso: sem site e site com problema, com `{nome}` e `{problema}` | prospeccao | **Adotar** (fase 5) |
| Teto diário de abordagens (padrão 15) para proteger o número | prospeccao | **Adotar** como "fila do dia" na tela (fase 5) |
| Página de demonstração em `/s/<slug>` servida a partir do banco, um app só | VitrineAI | **Adotar** para a prévia local (fase 5) |
| "Preparar pasta do cliente": dados reais + diagnóstico só com fatos + prompt para um agente personalizar o site e listar o que perguntar ao cliente | `rafaelcaetite/caca-cliente` | **Adotar** com o Claude Code, sem API paga (fase 5) |
| Verificação de site com **prova local**: o site só é do negócio se tiver o telefone ou duas palavras do endereço; só o nome bate = "talvez" | prospeccao | **Adotar** (fase 6) |
| Domínio provável a partir do nome (`nome.com.br`, `nome.com`) | prospeccao, `hectorautomacoesdev/fabrica-de-sites` | **Adotar** (fase 6), sempre com prova local; HEAD < 400 sozinho aceita domínio estacionado |
| Problema no site só quando é definitivo (DNS inexistente, 404 repetido, certificado inválido); 403, 429, 5xx e timeout nunca contam | prospeccao | **Adotar** (fase 6) |
| Base aberta do CNPJ da Receita como fonte de contato: estudo com cerca de 89% com telefone e 81% com e-mail, contra cerca de 12% no OpenStreetMap; ressalva de que muitos contatos são do contador | fabrica-de-sites (`experimentos/cnpj/RELATORIO.md`) | **Adotar** (fase 8, decidir após a segunda pausa) |
| Busca por cidade em vez de bairro | VitrineAI | **Adotar** só para segmentos esparsos (fase 7) |
| Envio pela "esteira" n8n com Evolution API | caca-cliente | **Descartar** (WhatsApp não oficial e disparo automático) |
| Google Places API | caca-cliente, prospeccao | **Descartar** (cartão e custo, decisão já tomada) |
| Serper.dev | fabrica-de-sites | **Descartar** (raspagem do Google por intermediário) |
| Instagram via Apify | caca-cliente | **Descartar** (viola os termos da Meta) |
| Nota de 0 a 100 com avaliações e número de avaliações | caca-cliente | **Descartar** (o OpenStreetMap não tem esse dado) |
| Avisos diários no Telegram por GitHub Actions | prospeccao | **Descartar por enquanto** (a ferramenta é local; a fila do dia resolve) |
| Painel React e sistema multiagente | fabrica-de-sites | **Descartar** (peso sem ganho para uma tela só) |
| Etapas "Protótipo enviado" e "Reunião" | caca-cliente | **Descartar por enquanto** (exige recriar a tabela; `contatado` com vitrine cobre) |

## Vocabulário de presença digital

Estados do site, explícitos e mutuamente exclusivos:

- `nao_verificado`: nenhum dado ainda.
- `sem_site_na_fonte`: o OpenStreetMap não informa site. Não prova que não exista.
- `so_rede_social`: o campo de site aponta para rede social, página de links (Linktree e similares), delivery ou WhatsApp. Não é site próprio.
- `site_informado`: URL própria cadastrada, ainda não testada.
- `site_ok`, `site_com_problemas` (sem HTTPS, sem `viewport`, resposta de erro) e `site_inacessivel`: resultados da verificação (fase 6). A checagem de mobile é uma heurística pela tag `viewport` e a interface deve dizer isso.
- `ausencia_confirmada`: **só por ação manual minha**, após conferir no Google. Reversível e com data.

## Ofertas (o que vender a cada lead)

Cada lead recebe zero ou mais ofertas, cada uma com o motivo:

| Oferta | Quando |
|---|---|
| Landing page | `sem_site_na_fonte` ou `ausencia_confirmada` |
| Página própria | `so_rede_social` com rede social ou página de links |
| Cardápio próprio | `so_rede_social` com link de delivery (argumento: pedido direto, sem comissão) |
| Cardápio digital com QR code | segmento de comida sem site próprio |
| Site com domínio próprio | site em subdomínio gratuito (`wixsite.com`, `sites.google.com`, `blogspot.com` e similares) |
| Reformulação do site | `site_com_problemas` ou `site_inacessivel` |

---

## Fase 1: Auditoria e desenho — **concluída em 03/11/2026**

## Fase 2: Dados e ingestão — **concluída em 03/11/2026**

Pendência: a reimportação real com o código novo não rodou (Overpass com 502). Validar na primeira busca repetida.

## Fase 3: Pontuação explicável e ofertas — **concluída em 03/11/2026**

## Fase 4: Checagem manual, filtros, favoritos e exportação CSV — **concluída em 03/11/2026**

## Primeira pausa para prospectar — **concluída em 07/11/2026**

5 leads abordados com a pergunta "quer um site?", 5 sem interesse. Ver "O que os dados reais mostraram".

---

## Fase 5: Vitrine, mensagem e abordagem — **concluída em 08/11/2026**

Desvios do texto abaixo, aprovados pelo Matheus: a vitrine tem **um script fixo com hash no CSP** (em vez de nenhum JavaScript), fontes do Google Fonts, mapa do OpenStreetMap embutido e fotos do Unsplash em beleza e pet; **conteúdo de exemplo marcado "MODELO" é permitido** na prévia e é substituído pelos campos que o Matheus preenche. Detalhes e riscos na seção "Fase 5" do CLAUDE.md. Próximo passo: segunda pausa para prospectar.

O objetivo desta fase é transformar um lead numa abordagem concreta em poucos minutos: prévia com o nome do negócio, mensagem pronta com o link, envio manual e acompanhamento. É a fase que mais influencia fechar cliente, por isso vem antes de qualquer melhoria de descoberta.

**Antes de codar, apresente e espere eu escolher:**
- O desenho do modelo base da vitrine (estrutura das seções e como a cor e o texto variam por segmento), com uma captura de um lead de exemplo.
- Os textos de `SEGMENT_COPY` e de `MESSAGES` para os segmentos que já existem. Os textos são meus: proponha, eu aprovo ou reescrevo.

**Entregas**

*Vitrine*
- Módulo `vitrines.py` com funções puras: `slug_for(lead, existing)`, `content_for(lead, overrides)` e `render(content, preview)`. Um **modelo base único** em `templates/vitrine.html` (HTML e CSS, sem JavaScript), preenchido com `string.Template`, e um dicionário `SEGMENT_COPY` no topo do módulo com, por segmento: título da seção principal, chamada, até 4 destaques genéricos verdadeiros (por exemplo "Atendimento pelo WhatsApp", nunca "10 anos de tradição") e cor. Segmento sem texto próprio usa um texto neutro.
- Conteúdo vindo só do lead: nome, segmento, bairro, cidade, endereço, telefone, WhatsApp (só `manual_whatsapp` ou telefone `celular`), Instagram, e os campos que eu editar. Campo ausente **omite a seção**, nunca vira texto de exemplo.
- Botão principal: WhatsApp quando houver número de WhatsApp válido; senão, "Ligar" (`tel:`). Botão "Como chegar" com link de busca do mapa montado pelo código.
- Segmentos de comida (`FOOD_SEGMENTS`) ganham a seção "Cardápio" só se eu cadastrar itens; senão, a chamada "Peça pelo WhatsApp". Segmentos de saúde (clínica, dentista, veterinário) usam texto neutro, sem promessa de resultado.
- Enquanto `aprovado` for falso: faixa fixa "Prévia criada para {nome}", `<meta name="robots" content="noindex, nofollow">` e rodapé "Página de demonstração". Aprovado: sem faixa e sem `noindex`.
- CSP no próprio HTML: `default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'`.
- Tabela `vitrines` em migração aditiva com backup: `lead_id` (único), `slug` (único, `[a-z0-9-]{3,60}`), `content` (JSON com os campos editados por mim), `approved`, `created_at`, `updated_at`, `exported_at`. Slug repetido ganha o bairro e, se ainda repetir, um número.
- Rotas: `POST /api/leads/{id}/vitrine` (cria ou devolve a existente), `GET /s/{slug}` (prévia local renderizada do banco), `PATCH /api/vitrines/{slug}` (campos editáveis e `approved`), `POST /api/vitrines/{slug}/export` (grava `index.html` em `<LEADFINDER_VITRINES_DIR>/<slug>/`; padrão `vitrines_publicadas/`, no `.gitignore`).
- A base pública das prévias vem de `LEADFINDER_VITRINE_BASE` (por exemplo a URL do meu projeto de hospedagem estática). Sem ela, a interface avisa que o link ainda não pode ser enviado e mostra só a prévia local.
- Lead descartado ou "não contatar" não gera nem exporta vitrine.

*Mensagem e abordagem*
- Módulo `mensagens.py`, puro, com `MESSAGES` no topo: um texto por caso (`sem_site`, `so_rede_social`, `delivery`, `site_com_problemas`) mais um texto de `follow_up`. Placeholders: `{nome}`, `{bairro}`, `{segmento}`, `{link}` e `{problema}`. Escolha do caso pela oferta principal do lead. Regras: até 400 caracteres depois de preenchido, sem as palavras "IA", "inteligência artificial", "desenvolvedor" e "tecnologia", e termina com um pedido pequeno (olhar o link), nunca com "quer um site?".
- No painel do lead: a mensagem preenchida e editável, "Abrir WhatsApp com a mensagem" (`https://wa.me/55{numero}?text=...` com o texto codificado) e "Copiar mensagem". Sem número de WhatsApp, só "Copiar". O texto final que eu editar não é guardado.
- Botão "Enviei": muda a etapa para `contatado` (o histórico já existe) e grava a data. Abrir o WhatsApp **não** muda a etapa sozinho, porque abrir não é enviar.
- **Fila do dia:** filtro novo "Para abordar hoje" com leads não abordados, com canal de contato, sem "não contatar" e com vitrine criada, ordenados como hoje. Constante `DAILY_LIMIT = 15`: o topo da tela mostra "abordados hoje: n de 15" a partir de `status_changes`, e a fila mostra no máximo o que falta para o limite.
- **Follow-up:** filtro "Fazer follow-up" com leads em `contatado` há `FOLLOW_UP_DAYS = 3` dias ou mais, sem `follow_up_at`. O painel mostra a mensagem de follow-up e o botão "Enviei o follow-up" grava `follow_up_at` (coluna nova, migração aditiva). Um follow-up só por lead.
- **Não contatar:** coluna `do_not_contact_at` (migração aditiva), botão no painel, reversível. Lead marcado sai da fila, do follow-up e da prévia de busca (não volta como recomendado).

*Pasta do cliente*
- `POST /api/vitrines/{slug}/folder` cria `clientes/<slug>/` (no `.gitignore`) com `dados.json` (dados do lead, origem e data de cada campo, conteúdo da vitrine) e `PROMPT.md` com as regras para eu personalizar a vitrine no Claude Code: usar só dados reais, não inventar preço, depoimento ou avaliação, manter HTML e CSS sem JavaScript, e terminar com `RELATORIO.md` listando o que perguntar ao dono e o que conferir antes de enviar. Recomendado depois que o dono responder com interesse; disponível sempre.

**Testes obrigatórios:** escape de nome, endereço e campos editados (`<script>`, aspas, `&`), CSP e ausência de `<script>` no HTML gerado, slug (normalização, acentos, colisão com bairro e número, rejeição fora do padrão), seção omitida quando falta dado, WhatsApp só para celular ou manual, "Ligar" como alternativa, faixa e `noindex` só sem aprovação, exportação restrita à pasta (slug com `..` ou barra é recusado), lead descartado ou "não contatar" sem vitrine, escolha da mensagem por oferta, placeholders, limite de 400 caracteres e palavras proibidas, codificação do texto no `wa.me`, "Enviei" grava a etapa e abrir o WhatsApp não grava, fila do dia com limite e relógio injetado, follow-up com relógio injetado e uma vez só, "não contatar" fora da fila, do follow-up e dos recomendados da busca, migrações sem perda de dados, pasta do cliente com os dois arquivos e sem dado inventado.

**Aceite:** criar a vitrine de um lead real, abri-la em `/s/{slug}`, exportar, publicar à mão no meu projeto de hospedagem, abrir o WhatsApp com a mensagem e o link, e marcar "Enviei". O que depender da hospedagem fica com instrução de validação na minha máquina. **Pare.**

## Segunda pausa: abordar com prévia

Antes de qualquer fase seguinte: abordar de 10 a 15 leads com prévia e mensagem nova, respeitando a fila do dia, e fazer o follow-up de quem não respondeu. Depois, me conte quantos responderam, quantos se interessaram e o que fez falta. Se em 15 abordagens com prévia ninguém responder com interesse, o problema é a oferta, o público ou a mensagem, não a ferramenta: revisamos isso antes de qualquer código. A resposta decide a ordem das fases 6, 7 e 8 (ou nenhuma).

## Fase 6: Verificação e enriquecimento de sites (decidir após a segunda pausa)

Escreva **primeiro** o módulo de fetch guardado e os testes de segurança. Só depois a verificação e o enriquecimento.

**Entregas**
- Módulo de fetch conforme as restrições permanentes.
- **Verificação de "sem site"** para leads em `sem_site_na_fonte` ou `so_rede_social`: domínio provável a partir do nome (sem palavras genéricas do segmento, como "barbearia" e "restaurante"), testando `.com.br` e `.com`, pelo fetch guardado. O site só conta como do negócio com **prova local**: o telefone (8 últimos dígitos) ou pelo menos duas palavras não genéricas do endereço aparecem na página. Só o nome bate: estado novo `site_talvez`, com o endereço encontrado, para eu conferir. Nada encontrado: o estado não muda, porque não achar não prova ausência. Regras e listas de palavras genéricas em dicionários no topo do módulo.
- Enriquecimento, **apenas para leads com site próprio informado ou provado**: tentar HTTPS e depois HTTP e `www` (máximo 4 tentativas), página inicial mais até 3 páginas encontradas pelo texto do link (contato, fale conosco, atendimento, sobre, quem somos, localização, cardápio, menu).
- Extração: e-mails (`mailto`, texto e a forma "nome [at] dominio [dot] com"), classificados em próprio, genérico ou inválido (regras em **uma única fonte**); a busca continua até achar um e-mail do domínio próprio. Perfis de Instagram, Facebook, LinkedIn, X, TikTok e YouTube (nunca links de compartilhar nem perfis de plataformas). HTTPS, presença da tag `viewport` e presença de cardápio (link ou PDF).
- Problema no site **só quando é definitivo**: domínio que não resolve em duas tentativas, 404 ou 410 repetido, certificado inválido, sem HTTPS depois dos redirecionamentos, sem `viewport`. 403, 429, 5xx e timeout viram `bloqueado` ou `timeout`, nunca problema. A frase do problema alimenta `{problema}` da mensagem `site_com_problemas`.
- Resultado gravado com data: `ok`, `bloqueado` (403, 429, página de desafio: registre e siga, sem tentar de novo com outros cabeçalhos), `timeout`, `erro`. A oportunidade de `site_com_problemas` passa a média ou alta pela quantidade de problemas. Restaurante com site e sem cardápio encontrado ganha a oferta "Cardápio digital".
- Execução sob demanda: botão por lead e "Verificar selecionados" com teto por vez, sequencial, pelo navegador. A falha de um site nunca esconde o lead.
- `site_talvez` entra no `CHECK` de `site_state`: se isso exigir recriar a tabela, apresente a migração antes, no mesmo formato da migração 3.

**Testes obrigatórios (sem rede real, com transporte simulado):** SSRF contra `localhost`, `127.0.0.1`, `10.x`, `172.16.x`, `192.168.x`, `169.254.169.254`, `::1`, `fc00::/7`, IPv4 mapeado, NAT64, IP em decimal e hexadecimal, hostname que resolve para IP privado, par privado no socket, redirecionamento para IP privado, laço e excesso de redirecionamentos, esquemas `file`, `ftp` e `gopher`, portas fora de 80 e 443, usuário e senha na URL; limite de bytes, timeout, prazo total, conteúdo que não é HTML, `robots.txt`, ordem e teto das tentativas, resultado `bloqueado`, regras de e-mail; prova local por telefone, por endereço, só pelo nome (`site_talvez`) e homônimo de outra cidade (não é do negócio); 403, 5xx e timeout nunca viram problema.

**Aceite:** todos os testes passando e uma verificação de ponta a ponta com um site simulado. **Pare.**

## Fase 7: Captação brasileira e busca por cidade (decidir após a segunda pausa)

Aproveite a infraestrutura de busca existente. **Não crie um segundo mecanismo de descoberta.**

**Entregas**
- **Área de busca por segmento:** constante `CITY_WIDE_SEGMENTS` com os segmentos esparsos (oficina, ótica, pet shop, confeitaria, sorveteria, veterinário, imobiliária, clínica). Para eles, a busca usa a área administrativa do município no Overpass (`area` com `admin_level=8`) em vez da caixa do bairro, e o bairro vira filtro na lista. Segmentos densos (restaurante, lanchonete, bar, café) continuam por bairro. Meça o tempo e o número de resultados de uma busca real por cidade antes de decidir a lista final, e me mostre.
- Nichos configuráveis, adicionados sem mudar a lógica, no dicionário `SEGMENTS`. Valide cada tag na documentação do OSM: se não houver tag confiável para um nicho, deixe-o de fora e me avise. Priorize comida, beleza, saúde e serviços locais.
- Busca com **vários segmentos e várias áreas** (bairros e cidades, com UF), resultados consolidados no mesmo `leads`, deduplicados entre cidades, segmentos e execuções.
- **Cache de geocodificação** no SQLite. Execução sequencial pelo navegador, com pausa entre chamadas, teto de combinações por execução (constante), recuo em 429, 502 e 504, e **limite de área** (cidade grande com segmento denso exige dividir por bairro).
- Buscas salvas (criar, listar, rodar, remover). Progresso, falha parcial e cancelamento na tela.

**Testes obrigatórios (sem rede real):** escolha da área por segmento, consulta por área administrativa, deduplicação entre cidades e segmentos, pausas com relógio injetado, cache de geocodificação, teto e limite de área, recuo, buscas salvas, validação dos nichos.

**Aceite:** uma execução com várias combinações usando fontes simuladas e leads consolidados na interface, mais a medição real de uma busca por cidade. **Pare.**

## Fase 8: Contatos pela base aberta do CNPJ (decidir após a segunda pausa)

Resolve o gargalo medido em 03/11/2026: falta de contato. É fonte de **contato e de existência**, não de site.

**Antes de codar, verifique e me mostre:**
- O caminho atual de download da Receita Federal. O estudo da fabrica-de-sites (junho de 2026) registra que os arquivos saíram do diretório HTTP antigo para um compartilhamento público acessado por WebDAV. **Não verificado por nós:** confirme na página oficial de dados abertos do CNPJ antes de usar.
- O tamanho dos arquivos de Estabelecimentos e de Empresas no mês mais recente, e uma estimativa do espaço e do tempo para importar só São Paulo.
- O mapeamento de cada segmento de `SEGMENTS` para CNAEs, para eu aprovar.

**Entregas**
- Script `cnpj.py` (biblioteca padrão: `csv`, `zipfile`, `sqlite3`), que lê os arquivos em fluxo, sem carregar tudo na memória, e grava só estabelecimentos **ativos** do município e dos CNAEs escolhidos numa tabela própria (`cnpj_establishments`), com data do dump. Nenhuma dependência nova; se o tempo medido for inaceitável, apresente DuckDB como alternativa com o motivo.
- Nome do negócio: nome fantasia do estabelecimento; sem ele, razão social do arquivo de Empresas.
- Cruzamento com os leads do OpenStreetMap por nome normalizado e endereço (logradouro e número), com o critério exposto em constantes. Contato vindo do CNPJ entra com origem `cnpj` e data do dump, **nunca** sobrescreve contato manual e não apaga o do mapa.
- Estabelecimentos do CNPJ sem par no mapa podem virar leads novos só pela prévia de busca, como hoje (nada é gravado sem eu marcar).
- **E-mail de contabilidade:** domínio ou nome com "contab", "contabil", "contador", "escritorio" e similares (lista no topo) é marcado como provável contador e não conta como canal do negócio.
- **LGPD:** MEI e empresário individual têm CPF e nome de pessoa física. Não guardar CPF, guardar só nome fantasia, telefone e e-mail comerciais, e respeitar "não contatar".
- Filtro novo "aberto há menos de N meses" a partir da data de início de atividade.

**Testes obrigatórios (com arquivos sintéticos pequenos):** leitura em fluxo de ZIP com CSV em latin-1 e `;`, filtro por situação, município e CNAE, nome fantasia e fallback, cruzamento com e sem par, contato manual preservado, origem e data gravadas, e-mail de contador, ausência de CPF no banco, filtro por data de abertura, reimportação idempotente.

**Aceite:** importação de um dump sintético e um cruzamento visível na interface, mais as instruções para eu rodar com o dump real. **Pare.**

## Fase 9: Excel, documentação e revisão final (decidir após a segunda pausa)

**Entregas**
- **XLSX** com `openpyxl` (única dependência nova, justificada no relatório; sem ela, a interface avisa com clareza). Respeita os filtros.
  - Aba **Leads**: as mesmas colunas do Leads CSV, linha de cabeçalho em negrito, painel congelado e filtros.
  - Aba **Resumo**: por cidade, UF e segmento: total, com telefone, com e-mail, com site identificado, só rede social, sem site na fonte, por oferta, oportunidades prioritárias, abordados, responderam e fechados. Tudo calculado a partir dos dados salvos, sem estimativas.
  - O `openpyxl` trata texto iniciado por `=` como fórmula: neutralize explicitamente.
- README e `CLAUDE.md` coerentes com o código. Atualize a seção "fora do escopo". Verifique cada afirmação contra o código.
- Revisão final: suíte inteira, app iniciando com o banco antigo, nada fora do escopo, nenhuma funcionalidade duplicada.

**Relatório final:**

| Item | Resultado | Evidência |
|---|---|---|
| Leads CSV e CSV completo | ... | ... |
| Checagem manual | ... | ... |
| Vitrine, mensagem e fila do dia | ... | ... |
| Follow-up e não contatar | ... | ... |
| Excel com Resumo | ... | ... |
| Site que é rede social | ... | ... |
| Verificação com prova local e enriquecimento | ... | ... |
| Busca por cidade e captação brasileira | ... | ... |
| CNPJ | ... | ... |
| Pontuação e ofertas | ... | ... |
| Migração sem perda de dados | ... | ... |
| Testes | ... | saída da suíte |
| Documentação | ... | ... |

Liste também o que **não** foi feito, os limites que restam e o que eu preciso validar à mão.