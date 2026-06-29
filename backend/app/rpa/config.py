from .systems.esaj import ESajRPA
from .systems.pje import PJeRPA
from .systems.eproc import EprocRPA
from .systems.projudi import ProjudiRPA
from .systems.tucujuris import TucujurisRPA
from .tjrj import TJRJRPA

# Mapeamento de Tribunais por Estado e Sistema
# Formato: "UF": {"system": SystemClass, "url": "URL"}
# TJRJ tem implementação customizada

TRIBUNAL_CONFIG = {
    "AC": {"system": ESajRPA, "url": "https://esaj.tjac.jus.br/cpopg/open.do", "name": "TJAC"},
    "AL": {"system": ESajRPA, "url": "https://www2.tjal.jus.br/cpopg/open.do", "name": "TJAL"},
    "AM": {"system": ESajRPA, "url": "https://consultasaj.tjam.jus.br/cpopg/open.do", "name": "TJAM"},
    "AP": {"system": PJeRPA, "url": "https://pje.tjap.jus.br/1g/ConsultaPublica/listView.seam", "name": "TJAP"},
    "BA": {"system": PJeRPA, "url": "https://pje.tjba.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJBA"},
    "CE": {"system": ESajRPA, "url": "https://esaj.tjce.jus.br/cpopg/open.do", "name": "TJCE"},
    "DF": {"system": PJeRPA, "url": "https://pje.tjdft.jus.br/consultapublica/ConsultaPublica/listView.seam", "name": "TJDF"},
    "ES": {"system": PJeRPA, "url": "https://pje.tjes.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJES"},
    "GO": {"system": ProjudiRPA, "url": "https://projudi.tjgo.jus.br/BuscaProcesso", "name": "TJGO"},
    "MA": {"system": PJeRPA, "url": "https://pje.tjma.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJMA"},
    "MG": {"system": PJeRPA, "url": "https://pje.tjmg.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJMG"},
    "MS": {"system": ESajRPA, "url": "https://esaj.tjms.jus.br/cpopg/open.do", "name": "TJMS"},
    "MT": {"system": PJeRPA, "url": "https://pje.tjmt.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJMT"},
    "PA": {"system": PJeRPA, "url": "https://pje.tjpa.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJPA"},
    "PB": {"system": PJeRPA, "url": "https://pje.tjpb.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJPB"},
    "PE": {"system": PJeRPA, "url": "https://pje.tjpe.jus.br/1g/ConsultaPublica/listView.seam", "name": "TJPE"},
    "PI": {"system": PJeRPA, "url": "https://pje.tjpi.jus.br/1g/ConsultaPublica/listView.seam", "name": "TJPI"},
    "PR": {"system": ProjudiRPA, "url": "https://projudi.tjpr.jus.br/projudi_consulta/", "name": "TJPR"},
    "RJ": {"system": TJRJRPA, "url": None, "name": "TJRJ"}, # Custom Implementation
    "RN": {"system": PJeRPA, "url": "https://pje.tjrn.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJRN"},
    "RO": {"system": PJeRPA, "url": "https://pje.tjro.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJRO"},
    "RR": {"system": PJeRPA, "url": "http://pje.tjrr.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJRR"}, # Alterado para PJe (Projudi exige login/captcha)
    "RS": {"system": EprocRPA, "url": "https://eproc1g.tjrs.jus.br/eproc/externo_controlador.php?acao=processo_consulta_publica_chave/consultar", "name": "TJRS"},
    "SC": {"system": EprocRPA, "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_consulta_publica", "name": "TJSC"},
    "SE": {"system": PJeRPA, "url": "https://pje.tjse.jus.br/pje/ConsultaPublica/listView.seam", "name": "TJSE"},
    "SP": {"system": ESajRPA, "url": "https://esaj.tjsp.jus.br/cpopg/open.do", "name": "TJSP"},
    "TO": {"system": EprocRPA, "url": "https://eproc1.tjto.jus.br/eprocV2_prod_1grau/externo_controlador.php?acao=processo_consulta_publica_chave/consultar", "name": "TJTO"},
}

def get_rpa_for_state(uf: str):
    config = TRIBUNAL_CONFIG.get(uf)
    if not config:
        return None
    
    system_class = config.get("system")
    if not system_class:
        return None
        
    if system_class == TJRJRPA:
        return TJRJRPA() # TJRJ não usa url no init da mesma forma ou tem fixa
    
    return system_class(base_url=config["url"], tribunal_name=config["name"])
