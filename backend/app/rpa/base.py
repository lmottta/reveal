from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseRPA(ABC):
    """
    Classe base para todos os módulos de RPA.
    Define a interface comum para execução de consultas.
    """

    @abstractmethod
    def search(self, query: str) -> Dict[str, Any]:
        """
        Executa a busca no tribunal específico.
        :param query: Termo de busca (ex: Nome, CNPJ, Processo)
        :return: Dicionário com os resultados encontrados.
        """
        pass

    def validate_input(self, query: str) -> bool:
        """
        Valida se o input é seguro e adequado para o tribunal.
        """
        # Implementação padrão, pode ser sobrescrita
        return len(query) > 3
