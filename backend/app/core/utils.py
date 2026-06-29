import re

# Mapa de códigos de tribunal estadual (Justiça Estadual - J=8) para UF
CNJ_STATE_MAP = {
    "01": "AC", "02": "AL", "03": "AP", "04": "AM", "05": "BA",
    "06": "CE", "07": "DF", "08": "ES", "09": "GO", "10": "MA",
    "11": "MT", "12": "MS", "13": "MG", "14": "PA", "15": "PB",
    "16": "PR", "17": "PE", "18": "PI", "19": "RJ", "20": "RN",
    "21": "RS", "22": "RO", "23": "RR", "24": "SC", "25": "SE",
    "26": "SP", "27": "TO"
}

def validate_cnj(cnj: str) -> bool:
    """
    Valida se um número de processo segue o padrão CNJ e se os dígitos verificadores estão corretos.
    Formato: NNNNNNN-DD.AAAA.J.TR.OOOO (20 dígitos)
    """
    clean_cnj = re.sub(r"\D", "", cnj)
    
    if len(clean_cnj) != 20:
        return False
        
    # Extrair partes
    # NNNNNNN DD AAAA J TR OOOO
    # 0123456 78 9012 3 45 6789
    
    num_sequencial = clean_cnj[:7]
    digito_verificador = int(clean_cnj[7:9])
    ano = clean_cnj[9:13]
    justica = clean_cnj[13]
    tribunal = clean_cnj[14:16]
    origem = clean_cnj[16:]
    
    # Montar número para cálculo (Módulo 97 Base 10)
    # NNNNNNN + AAAA + J + TR + OOOO + '00'
    # O cálculo correto é concatenar num_sequencial + ano + justica + tribunal + origem + "00"
    # E calcular o resto da divisão por 97.
    # DV = 98 - (resto % 97)
    
    # Correção da lógica de montagem para validação
    # A validação oficial CNJ usa o número completo sem os dígitos verificadores, 
    # adiciona "00" ao final, e calcula o resto por 97.
    # O número base é: NNNNNNN + AAAA + J + TR + OOOO + 00
    
    numero_base_str = f"{num_sequencial}{ano}{justica}{tribunal}{origem}00"
    
    try:
        numero_base = int(numero_base_str)
        resto = numero_base % 97
        digito_calculado = 98 - resto
        
        return digito_calculado == digito_verificador
    except ValueError:
        return False

def infer_state_from_cnj(cnj: str) -> str:
    """
    Infere a UF do estado a partir do número CNJ.
    Retorna None se não for Justiça Estadual (J=8) ou se o código não for encontrado.
    """
    clean_cnj = re.sub(r"\D", "", cnj)
    if len(clean_cnj) != 20:
        return None
    
    justica = clean_cnj[13]
    tribunal = clean_cnj[14:16]
    
    # Apenas Justiça Estadual (8)
    if justica != "8":
        return None
        
    return CNJ_STATE_MAP.get(tribunal)
