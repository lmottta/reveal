
import unicodedata

# Mapa CNJ para correção de integridade
CNJ_CODE_MAP = {
    "01": "TJAC", "02": "TJAL", "03": "TJAP", "04": "TJAM",
    "05": "TJBA", "06": "TJCE", "07": "TJDF", "08": "TJES",
    "09": "TJGO", "10": "TJMA", "11": "TJMT", "12": "TJMS",
    "13": "TJMG", "14": "TJPA", "15": "TJPB", "16": "TJPR",
    "17": "TJPE", "18": "TJPI", "19": "TJRJ", "20": "TJRN",
    "21": "TJRS", "22": "TJRO", "23": "TJRR", "24": "TJSC",
    "25": "TJSE", "26": "TJSP", "27": "TJTO"
}

RELEVANT_KEYWORDS = [
    "EXPLORACAO SEXUAL",
    "EXPLORACAO SEXUAL INFANTO JUVENIL",
    "ABUSO SEXUAL",
    "ABUSO SEXUAL INFANTIL",
    "ABUSO SEXUAL DE INCAPAZ",
    "ESTUPRO",
    "ESTUPRO DE VULNERAVEL",
    "VIOLENCIA SEXUAL",
    "TRAFICO SEXUAL",
    "TRAFICO DE PESSOAS",
    "PORNOGRAFIA INFANTIL",
    "PEDOFILIA",
    "ALICIAMENTO",
    "ABUSO DE MENOR",
    "ABUSO INFANTIL",
    "CRIME SEXUAL",
    "CRIMES SEXUAIS",
    "PREDADOR SEXUAL",
    "PREDADORES SEXUAIS",
    "EXPLORACAO DE VULNERAVEL",
    "VIOLENCIA SEXUAL CONTRA MULHER",
    "VIOLENCIA SEXUAL CONTRA MULHERES"
]

# Coordenadas fixas para cidades principais (MVP)
COORDS = {
    # SP
    "SÃO PAULO": {"lat": -23.5505, "lng": -46.6333},
    "CAMPINAS": {"lat": -22.9099, "lng": -47.0626},
    "SANTOS": {"lat": -23.9618, "lng": -46.3322},
    "RIBEIRÃO PRETO": {"lat": -21.1704, "lng": -47.8103},
    "SOROCABA": {"lat": -23.5015, "lng": -47.4521},
    "OSASCO": {"lat": -23.5336, "lng": -46.7920},
    "GUARULHOS": {"lat": -23.4542, "lng": -46.5333},
    "SAO PAULO": {"lat": -23.5505, "lng": -46.6333}, # Variação sem acento
    
    # Capitais e Cidades do RPA News
    "RIO BRANCO": {"lat": -9.9754, "lng": -67.8249},
    "MACEIO": {"lat": -9.6662, "lng": -35.7351},
    "MACAPA": {"lat": 0.0355, "lng": -51.0705},
    "MANAUS": {"lat": -3.1190, "lng": -60.0217},
    "SALVADOR": {"lat": -12.9777, "lng": -38.5016},
    "FORTALEZA": {"lat": -3.7172, "lng": -38.5434},
    "BRASILIA": {"lat": -15.7975, "lng": -47.8919},
    "VITORIA": {"lat": -20.3155, "lng": -40.3128},
    "GOIANIA": {"lat": -16.6869, "lng": -49.2648},
    "SAO LUIS": {"lat": -2.5391, "lng": -44.2829},
    "CUIABA": {"lat": -15.6014, "lng": -56.0979},
    "CAMPO GRANDE": {"lat": -20.4697, "lng": -54.6201},
    "BELO HORIZONTE": {"lat": -19.9167, "lng": -43.9345},
    "UBERLANDIA": {"lat": -18.9128, "lng": -48.2755},
    "CONTAGEM": {"lat": -19.9321, "lng": -44.0539},
    "BELEM": {"lat": -1.4558, "lng": -48.4902},
    "JOAO PESSOA": {"lat": -7.1195, "lng": -34.8450},
    "CURITIBA": {"lat": -25.4284, "lng": -49.2733},
    "LONDRINA": {"lat": -23.3045, "lng": -51.1696},
    "RECIFE": {"lat": -8.0476, "lng": -34.8770},
    "TERESINA": {"lat": -5.0919, "lng": -42.8034},
    "RIO DE JANEIRO": {"lat": -22.9068, "lng": -43.1729},
    "NITEROI": {"lat": -22.8859, "lng": -43.1153},
    "SAO GONCALO": {"lat": -22.8275, "lng": -43.0631},
    "NATAL": {"lat": -5.7945, "lng": -35.2110},
    "PORTO ALEGRE": {"lat": -30.0346, "lng": -51.2177},
    "CAXIAS DO SUL": {"lat": -29.1678, "lng": -51.1794},
    "PORTO VELHO": {"lat": -8.7612, "lng": -63.9039},
    "BOA VISTA": {"lat": 2.8235, "lng": -60.6758},
    "FLORIANOPOLIS": {"lat": -27.5954, "lng": -48.5480},
    "JOINVILLE": {"lat": -26.3045, "lng": -48.8487},
    "ARACAJU": {"lat": -10.9472, "lng": -37.0731},
    "PALMAS": {"lat": -10.1753, "lng": -48.3318},
    "DESCONHECIDO": {"lat": -15.7975, "lng": -47.8919} # Fallback Brasilia (Centro)
}

STATE_COORDS = {
    "AC": {"lat": -9.9754, "lng": -67.8249},
    "AL": {"lat": -9.6662, "lng": -35.7351},
    "AP": {"lat": 0.0355, "lng": -51.0705},
    "AM": {"lat": -3.1190, "lng": -60.0217},
    "BA": {"lat": -12.9777, "lng": -38.5016},
    "CE": {"lat": -3.7172, "lng": -38.5434},
    "DF": {"lat": -15.7975, "lng": -47.8919},
    "ES": {"lat": -20.3155, "lng": -40.3128},
    "GO": {"lat": -16.6869, "lng": -49.2648},
    "MA": {"lat": -2.5391, "lng": -44.2829},
    "MT": {"lat": -15.6014, "lng": -56.0979},
    "MS": {"lat": -20.4697, "lng": -54.6201},
    "MG": {"lat": -19.9167, "lng": -43.9345},
    "PA": {"lat": -1.4558, "lng": -48.4902},
    "PB": {"lat": -7.1195, "lng": -34.8450},
    "PR": {"lat": -25.4284, "lng": -49.2733},
    "PE": {"lat": -8.0476, "lng": -34.8770},
    "PI": {"lat": -5.0919, "lng": -42.8034},
    "RJ": {"lat": -22.9068, "lng": -43.1729},
    "RN": {"lat": -5.7945, "lng": -35.2110},
    "RS": {"lat": -30.0346, "lng": -51.2177},
    "RO": {"lat": -8.7612, "lng": -63.9039},
    "RR": {"lat": 2.8235, "lng": -60.6758},
    "SC": {"lat": -27.5954, "lng": -48.5480},
    "SP": {"lat": -23.5505, "lng": -46.6333},
    "SE": {"lat": -10.9472, "lng": -37.0731},
    "TO": {"lat": -10.1753, "lng": -48.3318}
}

# Mapeamento Tribunal -> Estado
TRIBUNAL_TO_STATE = {
    "TJSP": "SP",
    "TJRJ": "RJ",
    "TJMG": "MG",
    "TJRS": "RS",
    "TJPR": "PR",
    "TJBA": "BA",
    "TJSC": "SC",
    "TJGO": "GO",
    "TJPE": "PE",
    "TJCE": "CE",
    "TJDF": "DF",
    "TJES": "ES",
    "TJMT": "MT",
    "TJMS": "MS",
    "TJPA": "PA",
    "TJPB": "PB",
    "TJMA": "MA",
    "TJRN": "RN",
    "TJAL": "AL",
    "TJPI": "PI",
    "TJSE": "SE",
    "TJRO": "RO",
    "TJTO": "TO",
    "TJAC": "AC",
    "TJAP": "AP",
    "TJRR": "RR"
}
