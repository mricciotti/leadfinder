# Leadfinder

Ferramenta pessoal de prospecção. Busca negócios locais no OpenStreetMap (Nominatim e Overpass), mostra a situação do site de cada um, diz o que oferecer (landing page, página própria, cardápio, domínio próprio, reformulação) com a prioridade e os motivos, e controla o funil de contato (novo, contatado, respondeu, fechado, descartado). Cada lead pode receber a sua checagem manual (telefone, WhatsApp, Instagram, site, ou "não tem site"), e a lista filtrada pode ser vista na tela (seção Planilha, as mesmas colunas do arquivo) ou baixada em Leads CSV ou CSV completo, prontos para o Excel. Há também uma visão de funil em colunas. A seção Buscar procura negócios novos no mapa e lista as áreas que você já buscou.

"Sem site no mapa" não significa "sem site". Confira cada lead antes de abordar.

## Como rodar

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest
python -m uvicorn main:app
```

Linux ou macOS: troque a segunda linha por `source .venv/bin/activate`.

A interface fica em `http://localhost:8000`. O banco é o `leads.db`, na pasta do projeto (a variável `LEADFINDER_DB` muda o caminho). Quando o esquema muda, o banco é copiado antes para `leads.db.bak-AAAAMMDD-HHMMSS`.

Arquitetura, decisões, limites e regras de trabalho estão no [CLAUDE.md](CLAUDE.md).

## Créditos

Dados de negócios e de bairros: © colaboradores do OpenStreetMap, licença ODbL (https://www.openstreetmap.org/copyright). A lista de bairros de São Paulo fica em `bairros_sp.json` e se atualiza com `python places.py`.

Algumas regras de limpeza de URL e de reconhecimento de redes sociais foram adaptadas das ideias do [google-maps-scraper-kit](https://github.com/Mahanaicoach/google-maps-scraper-kit) (licença MIT). O mecanismo de coleta dele não é usado aqui.
