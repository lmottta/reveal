from abc import ABC, abstractmethod
from typing import Dict, Any, List
import re

class BaseSystemRPA(ABC):
    """
    Classe base para sistemas de tribunais (PJe, e-SAJ, Projudi, Eproc, etc).
    """

    def __init__(self, base_url: str, tribunal_name: str):
        self.base_url = base_url
        self.tribunal_name = tribunal_name

    @abstractmethod
    def search(self, query: str) -> Dict[str, Any]:
        """
        Executa a busca no sistema.
        """
        pass

    def validate_input(self, query: str) -> bool:
        """
        Valida se o input é adequado para o sistema.
        Permite CNJ (20 dígitos) ou busca por nome (string não vazia).
        """
        if not query:
            return False
            
        # Se for numérico, valida tamanho do CNJ
        clean_query = re.sub(r"\D", "", query)
        if clean_query.isdigit() and len(clean_query) == len(query):
             return len(clean_query) == 20
             
        # Se tem letras, assume que é nome e permite (min 3 chars)
        return len(query.strip()) >= 3
