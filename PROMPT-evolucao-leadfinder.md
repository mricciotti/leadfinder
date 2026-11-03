# Leadfinder: evolução para inteligência comercial local (prompt em fases)

## Como trabalhar neste prompt

- Leia o `CLAUDE.md` inteiro antes de qualquer coisa. Ele prevalece sobre este texto, exceto onde este prompt o atualiza de forma explícita.
- Execute **uma fase por vez**. Ao terminar, entregue o relatório da fase (o que mudou, arquivos tocados, saída dos testes, decisões tomadas, riscos, pendências) e **pare**. Só comece a próxima quando eu escrever "seguir".
- Discorde quando uma ideia, minha ou sua, for ruim: diga o motivo e proponha uma alternativa com trade-offs. Decisões não triviais passam pelo "tribunal" do `CLAUDE.md`.
- Nada de commit, push, PR, merge ou deploy sem minha autorização explícita.
- Código: arquivos completos, sem comentários, padrões que já existem, mudanças cirúrgicas, simplicidade primeiro, testes junto com o código. Nenhuma dependência nova sem justificativa. A única prevista é `openpyxl`, na fase 7.
- Não declare que algo funciona sem executar. O que depende de rede externa (Overpass, Nominatim, sites de terceiros) e não puder ser validado aqui, teste com dados simulados e me diga como validar na minha máquina.
- Documentação: cada fase atualiza o README e o `CLAUDE.md` apenas no que mudou. Fonte única de verdade. Não crie `AGENTS.md` nem arquivos duplicados.
- Se encontrar um bloqueio técnico, resolva da forma mais simples e segura. Se a solução alterar o escopo, pergunte antes.

## Objetivo

Encontrar negócios locais que precisam de **site, landing page, página de apresentação ou cardápio digital**, para eu fazer e vender. A ferramenta descobre, verifica a presença digital, diz **o que oferecer** a cada lead com justificativa, organiza a prospecção e exporta listas para abordagem individual. Continua em Python, FastAPI, SQLite e HTML puro, com OpenStreetMap, Overpass e Nominatim, custo zero e uso pessoal.

## O que os dados reais mostraram (03/11/2026)

Busca real de restaurantes em Pinheiros: 61 lugares, 54 sem site na fonte, 7 com site próprio (nenhum era rede social), 11 com telefone (todos fixos), **nenhum** com Instagram, e-mail ou WhatsApp. O Overpass levou 26 s por busca e respondeu 502 em 2 de 5 chamadas. O Nominatim devolveu a estação de trem de Pinheiros em vez do bairro.

Consequência: o gargalo é **conseguir contato**, não verificar site. A checagem manual registrada vale mais que automação nesta etapa. As fases 3 e 4 foram ajustadas para isso, e as fases 5, 6 e 7 só são decididas depois de uma pausa para prospectar.

## Estado conhecido (após a Fase 2, confira antes de cada fase)

- `contacts.py`: funções puras `normalize_phone` (DDD, fixo, celular, `+55`), `normalize_uf`, `normalize_url` (só http e https, sem credenciais, sem `utm_`) e `classify_url` (domínios em `URL_KINDS`).
- `overpass.py`: 8 segmentos fixos. `parse_places` mantém todos os lugares com nome e classifica o campo de site (`presence`). UF vem do Nominatim (`ISO3166-2-lvl4`) quando o endereço não tem.
- `db.py`: migração aditiva por `PRAGMA user_version` com backup `leads.db.bak-*`. Upsert que atualiza dados do mapa sem tocar em status, anotações e favorito. Deduplicação pelo ID do OSM com fallback ponto e área (mesmo nome, cerca de 50 m).
- `main.py`: `GET /`, `GET /api/segments`, `GET /api/leads`, `POST /api/search` (devolve `total`, `found`, `without_site`, `added`), `PATCH /api/leads/{id}`.
- `static/index.html`: lista em linhas, funil por etapa, filtro por segmento e bairro, estado do site por linha. A pontuação exibida ainda é a de completude (0 a 6).
- 105 testes. Não existem: notas de oportunidade, favoritos na interface, histórico, exportação, enriquecimento, busca em várias cidades.
- Pendências conhecidas da interface: (a) após uma busca sem leads novos, ou com o bairro escrito diferente, o filtro esconde todos os leads; (b) o botão de Instagram só aparece com handle cadastrado.

## Decisões já tomadas

- Notas e motivos são **calculados na leitura** por uma função pura, sem colunas no banco.
- Histórico de etapas em tabela própria, na Fase 4.
- "Não contatar" será coluna, não etapa (o `CHECK` não muda sem recriar a tabela).
- Estado de execução de buscas em lote e de verificações fica no navegador (laço que chama a API uma vez por item), não em fila no servidor.

## Restrições permanentes (valem em todas as fases)

**Fontes e limites**
- Não incorporar o scraper do Google Maps, proxies, troca de user agent para driblar limites, bypass de CAPTCHA, Cloudflare ou antibot.
- Não decodificar proteções de e-mail de sites (inclui `data-cfemail` do Cloudflare). Se o site bloquear ou ofuscar, registre "bloqueado" ou "sem e-mail encontrado" e siga em frente.
- Não criar nenhum disparo automático de mensagens. O foco é abordagem individual.
- Nominatim e Overpass: `User-Agent` identificado, cache de geocodificação, no máximo 1 requisição por segundo ao Nominatim, execução sequencial, teto de combinações por execução e recuo exponencial em 429, 502 e 504.
- Não usar API paga nem IA onde regra determinística resolve.

**Dados**
- **Ausência de campo não é ausência de site.** Toda informação comercial guarda a origem (`osm`, `manual` ou `site`) e a data da coleta ou verificação.
- Nunca inventar dado. O OpenStreetMap não tem nota nem número de avaliações: não crie colunas fingindo esse dado, e avaliação nunca entra na pontuação.
- LGPD: minimização. Priorize contatos empresariais, registre a origem, e lead descartado ou marcado como "não contatar" não volta em novas buscas.
- Migrações só aditivas, com backup do `leads.db` antes.

**Requisições a sites de terceiros (módulo único e guardado, Fase 5)**
- Apenas `http` e `https`, portas 80 e 443, sem credenciais na URL.
- Resolver o DNS e bloquear IPs privados, loopback, link-local, reservados, multicast e o endereço de metadados da nuvem, incluindo IPv6, IPv4 mapeado em IPv6, 6to4 e NAT64.
- **Conferir também o IP do par no momento da conexão do socket**, o que fecha o DNS rebinding.
- Revalidar a cada redirecionamento (máximo 3). Timeout curto e prazo total por site, limite de bytes por resposta, apenas conteúdo HTML, respeitar `robots.txt`, no máximo 4 tentativas por lead e 4 páginas por site.
- Toda nova tentativa (esquema, `www`) passa pelo mesmo fetch guardado.

**Segurança geral**
- Proteção contra CSV Injection (células iniciadas por `=`, `+`, `-`, `@`, tab ou CR). O guard não pode corromper telefones que começam com `+`: exporte o telefone em formato nacional ou isente colunas validadas por padrão.
- SQL sempre parametrizado, entradas validadas, falha de fonte externa nunca derruba a aplicação nem esconde o lead, e logs sem dados pessoais.

## Referência analisada (`Mahanaicoach/google-maps-scraper-kit`, lida em 03/11/2026)

Licença MIT. Adaptar as ideias, não copiar código, e dar crédito no README. O motor de coleta dele (scraping do Maps com troca de user agent e rotação de proxies) é proibido aqui.

| Ideia | Origem | Decisão |
|---|---|---|
| Leads CSV com campos comerciais e redes sociais, nome de arquivo derivado da busca, filtro de e-mail aplicado também na exportação | #63 | **Adotar** (fase 4) |
| Regras de e-mail inválido em uma única fonte: no-reply, placeholders, tokens hexadecimais de 16 ou mais caracteres, `.gov` e `.mil`, fornecedores de marketing, nomes de arquivo como `logo@2x.png` | #63 | **Adotar** (fase 5) |
| Guard de fórmula que não corrompe telefone | master | **Adotar** (fase 4) |
| Retirar também `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`, sem recodificar a query quando nada sai. Reconhecer `fb.me`, `instagr.am`, `lnkd.in` | master, #64 | **Adotar** (fase 3, ajuste) |
| Fetch guardado com checagem do par no socket, prazo total e leitura limitada, só biblioteca padrão | master | **Adotar** (fase 5) |
| Outro esquema e `www`, sempre pelo fetch guardado. Seguir até achar e-mail do domínio próprio | #64 | **Adotar** (fase 5) |
| Redes sociais por expressão regular, ignorando links de compartilhar e perfis de plataformas (Wix, Shopify, iFood) | master | **Adotar** (fase 5) |
| Páginas de contato pelo texto do link, em português, incluindo "cardápio" | #64 | **Adotar** (fase 5) |
| Tag `viewport` como heurística de mobile | master | **Adotar** (fase 5) |
| Decodificar e-mail protegido pelo Cloudflare | #64 | **Descartar** |
| Pixels de anúncio, `intent_score`, verificação MX | master | **Descartar** (servem a quem já tem site e usam avaliações) |
| Divisão do mapa em grade, proxies, Docker | #46, master | **Descartar** |
| Documentação para mecanismos de IA, tabela comparativa | #36, #62 | **Descartar** |
| Branches sem PR | - | Nada a aproveitar (antigas ou já na master) |

## Vocabulário de presença digital

Estados do site, explícitos e mutuamente exclusivos:

- `nao_verificado`: nenhum dado ainda.
- `sem_site_na_fonte`: o OpenStreetMap não informa site. Não prova que não exista.
- `so_rede_social`: o campo de site aponta para rede social, página de links (Linktree e similares), delivery ou WhatsApp. Não é site próprio.
- `site_informado`: URL própria cadastrada, ainda não testada.
- `site_ok`, `site_com_problemas` (sem HTTPS, sem `viewport`, resposta de erro) e `site_inacessivel`: resultados da verificação (fase 5). A checagem de mobile é uma heurística pela tag `viewport` e a interface deve dizer isso.
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

## Fase 3: Pontuação explicável e ofertas

**Entregas** (módulo puro `scoring`, pesos e limites em dicionários no topo, sem rede)
- **Facilidade de contato:** telefone (celular vale mais), WhatsApp potencial (só celular), e-mail (próprio acima de provedor genérico como Gmail e Outlook, ambos válidos), Instagram, outras redes, endereço.
- **Oportunidade comercial:** `ausencia_confirmada` (máxima), `so_rede_social` (alta), `site_inacessivel` (alta), site em subdomínio gratuito (alta), `site_com_problemas` (média, a Fase 5 refina pela quantidade de problemas), `sem_site_na_fonte` (média, com o motivo "não verificado"), `site_informado` (indeterminada até testar), `site_ok` (baixa) e `nao_verificado` (**indeterminada**, nunca baixa).
- **Ofertas** conforme a tabela acima.
- **Prioridade:** alta quando a oportunidade é alta ou máxima e há pelo menos um canal de contato.
- Cada nota devolve nível e **lista de motivos em português**, e a interface os mostra num detalhe expansível por lead, com as ofertas visíveis na linha. A lista passa a ser ordenada por prioridade. Nenhum motivo pode usar avaliação ou número de avaliações, nem afirmar que o negócio está ativo.
- Ajuste herdado da referência: parâmetros de rastreamento e domínios curtos de redes no `contacts.py`.

**Testes obrigatórios:** uma regra por teste, os dois casos de exemplo (prioridade alta e oportunidade de reformulação), `nao_verificado` nunca resulta em oportunidade baixa, cada oferta, pesos alterados mudam o resultado, e leads antigos recebem nota sem erro.

**Aceite:** notas, motivos e ofertas visíveis na interface para todos os leads. **Pare.**

## Fase 4: Checagem manual, filtros, favoritos e exportação CSV

**Entregas**
- **Registro da checagem manual**, a peça mais importante desta fase: ao conferir um lead no Google, registrar o que encontrei (Instagram, WhatsApp, telefone, site real) com origem `manual` e data, ou "Confirmar que não tem site" (`ausencia_confirmada`, reversível). Dado manual nunca é sobrescrito por reimportação.
- Botão "Procurar Instagram" quando não houver handle (busca no Google pelo nome e bairro), e correção do filtro que esconde tudo (pendência a).
- **Filtros no servidor**, uma única função usada pela lista e pela exportação, com parâmetros combináveis: com site, sem site na fonte, só rede social, ausência confirmada, site com problemas, não verificado, com telefone, com e-mail, com Instagram, prioridade alta, por oferta, favoritos, ainda não abordados, mais os filtros atuais de segmento, bairro, cidade, UF e etapa.
- Favoritar (alternar) e tabela de histórico de etapas (lead, etapa, data).
- **Exportação pela interface**, com botões visíveis, "Leads CSV" como ação principal e "CSV completo" ao lado, sempre respeitando os filtros ativos. Sem lista, a interface avisa e **não gera arquivo vazio**.
- **Leads CSV**, quando disponível (sem inventar): nome, categoria, telefone, whatsapp potencial, link do WhatsApp, e-mail, tipo do e-mail, website, Instagram, Facebook, outras redes, endereço, cidade, UF, situação do site, ofertas, prioridade, nota de contato, nota de oportunidade, motivos (separados por " | "), origem e data da última verificação. Sem colunas de avaliação.
- **Formato:** UTF-8 com BOM, delimitador `;`, nome de arquivo com a busca e a data, guard de CSV Injection.

**Testes obrigatórios:** registro manual e sua preservação na reimportação, campos e ordem das colunas, BOM, delimitador, acentos (ã, ç, é), injeção (`=HYPERLINK(...)`, `+cmd`, `@SUM`), telefone sem corrupção, exportação respeitando cada filtro, exportação vazia sem arquivo, favoritos, histórico e persistência.

**Aceite:** registrar uma checagem manual e baixar o Leads CSV pela interface com filtros, abrindo corretamente no Excel pt-BR. **Pare.**

## Pausa: prospectar antes de continuar

Antes de qualquer fase seguinte: abordar de 10 a 20 leads reais e fazer mockup para 3 a 5. Depois, me conte o que fez falta na prática, e só então escolhemos entre as fases 5, 6 e 7 (ou nenhuma). Se em duas semanas não houver conversas, o problema não é a ferramenta.

## Fase 5: Verificação e enriquecimento de sites (decidir após a pausa)

Escreva **primeiro** o módulo de fetch guardado e os testes de segurança. Só depois o enriquecimento.

**Entregas**
- Módulo de fetch conforme as restrições permanentes.
- Enriquecimento, **apenas para leads com site próprio informado**: tentar HTTPS e depois HTTP e `www` (máximo 4 tentativas), página inicial mais até 3 páginas encontradas pelo texto do link (contato, fale conosco, atendimento, sobre, quem somos, localização, cardápio, menu).
- Extração: e-mails (`mailto`, texto e a forma "nome [at] dominio [dot] com"), classificados em próprio, genérico ou inválido (regras em **uma única fonte**); a busca continua até achar um e-mail do domínio próprio. Perfis de Instagram, Facebook, LinkedIn, X, TikTok e YouTube (nunca links de compartilhar nem perfis de plataformas). HTTPS, presença da tag `viewport` e presença de cardápio (link ou PDF).
- Resultado gravado com data: `ok`, `bloqueado` (403, 429, página de desafio: registre e siga, sem tentar de novo com outros cabeçalhos), `timeout`, `erro`. A oportunidade de `site_com_problemas` passa a média ou alta pela quantidade de problemas. Restaurante com site e sem cardápio encontrado ganha a oferta "Cardápio digital".
- Execução sob demanda: botão por lead e "Verificar selecionados" com teto por vez, sequencial, pelo navegador. A falha de um site nunca esconde o lead.

**Testes obrigatórios (sem rede real, com transporte simulado):** SSRF contra `localhost`, `127.0.0.1`, `10.x`, `172.16.x`, `192.168.x`, `169.254.169.254`, `::1`, `fc00::/7`, IPv4 mapeado, NAT64, IP em decimal e hexadecimal, hostname que resolve para IP privado, par privado no socket, redirecionamento para IP privado, laço e excesso de redirecionamentos, esquemas `file`, `ftp` e `gopher`, portas fora de 80 e 443, usuário e senha na URL; limite de bytes, timeout, prazo total, conteúdo que não é HTML, `robots.txt`, ordem e teto das tentativas, resultado `bloqueado`, e as regras de e-mail.

**Aceite:** todos os testes passando e uma verificação de ponta a ponta com um site simulado. **Pare.**

## Fase 6: Captação Brasileira (decidir após a pausa)

Aproveite a infraestrutura de busca existente. **Não crie um segundo mecanismo de descoberta.**

**Entregas**
- Nichos configuráveis, adicionados sem mudar a lógica. Decidir antes: manter no dicionário `SEGMENTS` (minha recomendação) ou mover para JSON. Valide cada tag na documentação do OSM: se não houver tag confiável para um nicho, deixe-o de fora e me avise. Priorize nichos do meu público (comida, beleza, saúde, serviços locais); os de varejo do PR #10 ficam como exemplo opcional.
- Busca com **vários segmentos e várias áreas** (bairros e cidades, com UF), resultados consolidados no mesmo `leads`, deduplicados entre cidades, segmentos e execuções.
- **Cache de geocodificação** no SQLite. Execução sequencial pelo navegador, com pausa entre chamadas, teto de combinações por execução (constante), recuo em 429, 502 e 504, e **limite de área** (cidade grande exige dividir por bairro).
- Buscas salvas (criar, listar, rodar, remover). Progresso, falha parcial e cancelamento na tela.

**Testes obrigatórios (sem rede real):** deduplicação entre cidades e segmentos, pausas com relógio injetado, cache de geocodificação, teto e limite de área, recuo, buscas salvas, validação dos nichos.

**Aceite:** uma execução com várias combinações usando fontes simuladas e leads consolidados na interface. **Pare.**

## Fase 7: Excel, documentação e revisão final (decidir após a pausa)

**Entregas**
- **XLSX** com `openpyxl` (única dependência nova, justificada no relatório; sem ela, a interface avisa com clareza). Respeita os filtros.
  - Aba **Leads**: as mesmas colunas do Leads CSV, linha de cabeçalho em negrito, painel congelado e filtros.
  - Aba **Resumo**: por cidade, UF e segmento: total, com telefone, com e-mail, com site identificado, só rede social, sem site na fonte, por oferta e oportunidades prioritárias. Tudo calculado a partir dos dados salvos, sem estimativas.
  - O `openpyxl` trata texto iniciado por `=` como fórmula: neutralize explicitamente.
- README e `CLAUDE.md` coerentes com o código. Atualize a seção "fora do escopo". Verifique cada afirmação contra o código.
- Revisão final: suíte inteira, app iniciando com o banco antigo, nada fora do escopo, nenhuma funcionalidade duplicada.

**Relatório final:**

| Item | Resultado | Evidência |
|---|---|---|
| Leads CSV e CSV completo | ... | ... |
| Checagem manual | ... | ... |
| Excel com Resumo | ... | ... |
| Site que é rede social | ... | ... |
| Verificação e enriquecimento | ... | ... |
| Captação Brasileira | ... | ... |
| Pontuação e ofertas | ... | ... |
| Migração sem perda de dados | ... | ... |
| Testes | ... | saída da suíte |
| Documentação | ... | ... |

Liste também o que **não** foi feito, os limites que restam e o que eu preciso validar à mão.
