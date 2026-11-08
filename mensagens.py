import re

MAX_LENGTH = 400

MESSAGES = {
    "sem_site": "Oi, tudo bem? Meu nome é Matheus. Vi o {nome} aqui em {bairro} e montei uma prévia de como poderia ser a página de vocês na internet, com endereço, telefone e botão de WhatsApp. Se puder dar uma olhada, é só abrir: {link}",
    "so_rede_social": "Oi, tudo bem? Meu nome é Matheus. Vi que o {nome} aparece nas redes sociais e montei uma prévia de uma página própria, com endereço e botão de WhatsApp, para quem procura {segmento} em {bairro} chegar mais fácil. Se puder dar uma olhada: {link}",
    "delivery": "Oi, tudo bem? Meu nome é Matheus. Vi o {nome} nos aplicativos de pedido e montei uma prévia de uma página própria, onde o cliente chama direto pelo WhatsApp. Se puder dar uma olhada: {link}",
    "site_com_problemas": "Oi, tudo bem? Meu nome é Matheus. Dei uma olhada no site do {nome} e vi que {problema}. Montei uma prévia de como ele poderia ficar. Se puder dar uma olhada: {link}",
    "follow_up": "Oi, tudo bem? Passando só para saber se você conseguiu ver a prévia que montei para o {nome}: {link}. Se não fizer sentido agora, sem problema: é só me avisar que eu não escrevo mais.",
}

FORBIDDEN = (
    re.compile(r"\bIA\b"),
    re.compile(r"intelig[eê]ncia artificial", re.I),
    re.compile(r"desenvolvedor", re.I),
    re.compile(r"tecnologia", re.I),
    re.compile(r"quer um site", re.I),
)

CASE_BY_OFFER = {
    "cardapio_proprio": "delivery",
    "pagina_propria": "so_rede_social",
    "reformulacao": "site_com_problemas",
}


def case_for(offers, problem=None):
    for offer in offers:
        case = CASE_BY_OFFER.get(offer["key"])
        if case == "site_com_problemas" and not problem:
            continue
        if case:
            return case
    return "sem_site"


def problems_with(text):
    found = []
    if len(text) > MAX_LENGTH:
        found.append(f"A mensagem tem {len(text)} caracteres. O limite é {MAX_LENGTH}.")
    for pattern in FORBIDDEN:
        if pattern.search(text):
            found.append(f"A mensagem contém uma expressão não permitida: {pattern.pattern}.")
    return found


def build(case, lead, link, segment_label, problem=None):
    text = MESSAGES[case].format(
        nome=lead["name"],
        bairro=lead["neighborhood"],
        segmento=segment_label.lower(),
        link=link,
        problema=problem or "",
    )
    return {"case": case, "text": text, "warnings": problems_with(text)}
