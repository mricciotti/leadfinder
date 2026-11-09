CITY = "São Paulo"
UF = "SP"

ZONES = {
    "centro": (
        "Centro",
        [
            "Sé", "República", "Bela Vista", "Consolação", "Santa Cecília",
            "Liberdade", "Bom Retiro", "Cambuci",
        ],
    ),
    "norte": (
        "Zona Norte",
        [
            "Santana", "Tucuruvi", "Mandaqui", "Jaçanã", "Tremembé", "Vila Maria",
            "Vila Guilherme", "Vila Medeiros", "Casa Verde", "Cachoeirinha", "Limão",
            "Brasilândia", "Freguesia do Ó", "Pirituba", "São Domingos", "Jaraguá",
            "Perus", "Anhanguera",
        ],
    ),
    "leste": (
        "Zona Leste",
        [
            "Mooca", "Água Rasa", "Belém", "Brás", "Pari", "Tatuapé", "Carrão",
            "Vila Formosa", "Aricanduva", "Penha", "Cangaíba", "Vila Matilde",
            "Artur Alvim", "Ponte Rasa", "Ermelino Matarazzo", "São Miguel",
            "Jardim Helena", "Vila Jacuí", "Itaim Paulista", "Vila Curuçá", "Itaquera",
            "José Bonifácio", "Parque do Carmo", "Cidade Líder", "Guaianases",
            "Lajeado", "Cidade Tiradentes", "São Mateus", "São Lucas", "Sapopemba",
            "Vila Prudente", "Iguatemi", "São Rafael",
        ],
    ),
    "sul": (
        "Zona Sul",
        [
            "Vila Mariana", "Saúde", "Moema", "Ipiranga", "Cursino", "Sacomã",
            "Jabaquara", "Campo Belo", "Santo Amaro", "Campo Grande", "Campo Limpo",
            "Capão Redondo", "Vila Andrade", "Jardim São Luís", "Jardim Ângela",
            "Socorro", "Cidade Dutra", "Grajaú", "Cidade Ademar", "Pedreira",
            "Parelheiros", "Marsilac",
        ],
    ),
    "oeste": (
        "Zona Oeste",
        [
            "Pinheiros", "Alto de Pinheiros", "Jardim Paulista", "Itaim Bibi",
            "Perdizes", "Lapa", "Barra Funda", "Vila Leopoldina", "Jaguara", "Jaguaré",
            "Butantã", "Morumbi", "Rio Pequeno", "Raposo Tavares", "Vila Sônia",
        ],
    ),
}


def label(key):
    return ZONES[key][0]


def districts(key):
    return ZONES[key][1]
