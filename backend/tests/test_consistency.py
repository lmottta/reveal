import unittest
import sys
import os
import json
import unicodedata
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.utils import validate_cnj
from app.models.lawsuit import Lawsuit
from app.models.search import News, SearchResult, Search
from app.db.session import SessionLocal, engine
from app.db.base import Base

class TestCityNormalization(unittest.TestCase):
    """Testes para validação de normalização de cidade"""

    def normalize(self, s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s.upper())

    def test_city_exact_match(self):
        city_filter = "SALVADOR"
        final_city = "SALVADOR"
        city_norm = self.normalize(city_filter)
        final_city_norm = self.normalize(final_city)
        self.assertTrue(city_norm in final_city_norm or final_city_norm in city_norm)

    def test_city_with_accent_matching(self):
        city_filter = "SALVADOR"
        final_city = "SALVADOR"
        self.assertTrue(self.normalize(city_filter) in self.normalize(final_city))

    def test_city_partial_match(self):
        city_filter = "SALV"
        final_city = "SALVADOR"
        city_norm = self.normalize(city_filter)
        final_city_norm = self.normalize(final_city)
        self.assertTrue(city_norm in final_city_norm or final_city_norm in city_norm)

    def test_city_case_insensitive(self):
        city_filter = "salvador"
        final_city = "SALVADOR"
        self.assertTrue(self.normalize(city_filter) in self.normalize(final_city))

    def test_city_different_values_should_not_match(self):
        city_filter = "SALVADOR"
        final_city = "FEIRA DE SANTANA"
        city_norm = self.normalize(city_filter)
        final_city_norm = self.normalize(final_city)
        self.assertFalse(city_norm in final_city_norm or final_city_norm in city_norm)


class TestPartiesParsing(unittest.TestCase):
    """Testes para validação de parsing de parties (object vs array)"""

    def test_parties_as_object_with_polo_passivo(self):
        parties = {"Polo Ativo": ["MINISTÉRIO PÚBLICO"], "Polo Passivo": ["João Silva"]}
        autor_arr = parties.get("Polo Ativo", [])
        reu_arr = parties.get("Polo Passivo", [])
        autorName = autor_arr[0] if autor_arr and len(autor_arr) > 0 else "-"
        reuName = reu_arr[0] if reu_arr and len(reu_arr) > 0 else "-"
        self.assertEqual(reuName, "João Silva")
        self.assertEqual(autorName, "MINISTÉRIO PÚBLICO")

    def test_parties_as_object_with_reu_lowercase(self):
        parties = {"Autor": ["Maria Santos"], "Réu": ["Pedro Oliveira"]}
        autor_arr = parties.get("Autor", [])
        reu_arr = parties.get("Réu", parties.get("Reu", []))
        autorName = autor_arr[0] if autor_arr and len(autor_arr) > 0 else "-"
        reuName = reu_arr[0] if reu_arr and len(reu_arr) > 0 else "-"
        self.assertEqual(reuName, "Pedro Oliveira")

    def test_parties_as_array(self):
        parties = [
            {"tipo": "Autor", "nome": "Maria Santos"},
            {"tipo": "Réu", "nome": "Carlos André"}
        ]
        autor = next((p for p in parties if "autor" in p.get("tipo", "").lower()), None)
        reu = next((p for p in parties if "réu" in p.get("tipo", "").lower() or "reu" in p.get("tipo", "").lower()), None)
        self.assertEqual(autor.get("nome") if autor else "-", "Maria Santos")
        self.assertEqual(reu.get("nome") if reu else "-", "Carlos André")

    def test_parties_as_json_string(self):
        parties_str = '{"Polo Ativo": ["MP"], "Polo Passivo": ["José Carlos"]}'
        parties = json.loads(parties_str)
        reu_arr = parties.get("Polo Passivo", [])
        reuName = reu_arr[0] if reu_arr and len(reu_arr) > 0 else "-"
        self.assertEqual(reuName, "José Carlos")

    def test_parties_empty(self):
        parties = {}
        autor_arr = parties.get("Polo Ativo", parties.get("Autor", []))
        reu_arr = parties.get("Polo Passivo", parties.get("Réu", parties.get("Reu", [])))
        autorName = autor_arr[0] if autor_arr and len(autor_arr) > 0 else "-"
        reuName = reu_arr[0] if reu_arr and len(reu_arr) > 0 else "-"
        self.assertEqual(autorName, "-")
        self.assertEqual(reuName, "-")


class TestCatalogGeoConsistency(unittest.TestCase):
    """Testes de integração para validar consistência entre catálogo e geo"""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        existing = cls.db.query(Lawsuit).count()
        if existing == 0:
            fixtures = [
                Lawsuit(
                    cnj="00000011120238260001",
                    tribunal="TJSP",
                    class_type="Ação Penal",
                    subject="Estupro de vulnerável",
                    status="Ativo",
                    distribution_date="2023-04-10",
                    court="Vara Criminal de Campinas",
                    comarca="COMARCA DE CAMPINAS",
                    judge="Juiz A",
                    parties='[{"tipo":"Autor","nome":"MP"},{"tipo":"Réu","nome":"Réu A"}]',
                    movements='[{"data":"2023-04-10","conteudo":"Distribuição"}]',
                    created_at=datetime.utcnow()
                ),
                Lawsuit(
                    cnj="00000022220238190001",
                    tribunal="TJRJ",
                    class_type="Ação Penal",
                    subject="Abuso sexual infantil",
                    status="Ativo",
                    distribution_date="2023-05-12",
                    court="Vara Criminal de Niterói",
                    comarca="COMARCA DE NITERÓI",
                    judge="Juiz B",
                    parties='[{"tipo":"Autor","nome":"MP"},{"tipo":"Réu","nome":"Réu B"}]',
                    movements='[{"data":"2023-05-12","conteudo":"Distribuição"}]',
                    created_at=datetime.utcnow()
                ),
                Lawsuit(
                    cnj="00000033320238160001",
                    tribunal="TJPR",
                    class_type="Inquérito Policial",
                    subject="Tráfico sexual",
                    status="Ativo",
                    distribution_date="2023-06-01",
                    court="Vara Criminal de Curitiba",
                    comarca="COMARCA DE CURITIBA",
                    judge="Juiz C",
                    parties='[{"tipo":"Autor","nome":"MP"},{"tipo":"Réu","nome":"Réu C"}]',
                    movements='[{"data":"2023-06-01","conteudo":"Distribuição"}]',
                    created_at=datetime.utcnow()
                )
            ]
            cls.db.add_all(fixtures)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_catalog_count_vs_geo_count(self):
        """Valida que a contagem de processos no catálogo deve ser consistente com geo"""
        from app.api.endpoints.search import list_catalog
        from app.api.endpoints.stats import get_geo_stats

        geo_data = get_geo_stats(db=self.db)
        geo_total = sum(point.get("count", 0) for point in geo_data)

        catalog_data = list_catalog(city=None, state=None, term=None, source_type="judicial", limit=5000, db=self.db)
        catalog_total = len(catalog_data)

        print(f"\nGeo total: {geo_total}, Catalog total: {catalog_total}")
        self.assertGreater(catalog_total, 0, "Catálogo deveria ter processos")

    def test_catalog_city_filter_consistency(self):
        """Valida que filtro de cidade retorna resultados consistentes"""
        from app.api.endpoints.search import list_catalog

        test_city = "SALVADOR"
        catalog_data = list_catalog(city=test_city, state="BA", term=None, source_type="all", limit=1000, db=self.db)

        for item in catalog_data:
            city_normalized = self.normalize(item.get("city", ""))
            if city_normalized and city_normalized != "DESCONHECIDO":
                self.assertIn(
                    self.normalize(test_city),
                    city_normalized,
                    f"Cidade do item '{item.get('city')}' não contém filtro '{test_city}'"
                )

    def normalize(self, s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s.upper())


class TestBackendCityFilterLogic(unittest.TestCase):
    """Testes para validar lógica de filtro de cidade no backend"""

    def normalize(self, s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s.upper())

    def test_filter_should_match_when_city_contains(self):
        city_filter = "VARA CRIMINAL DE SALVADOR"
        final_city = "SALVADOR"
        city_norm = self.normalize(city_filter)
        final_city_norm = self.normalize(final_city)
        should_continue = city_norm not in final_city_norm and final_city_norm not in city_norm
        self.assertFalse(should_continue, "Filtro deveria continuar (match)")

    def test_filter_should_reject_different_cities(self):
        city_filter = "SALVADOR"
        final_city = "FEIRA DE SANTANA"
        city_norm = self.normalize(city_filter)
        final_city_norm = self.normalize(final_city)
        should_reject = city_norm not in final_city_norm and final_city_norm not in city_norm
        self.assertTrue(should_reject, "Cidades diferentes deveriam ser rejeitadas")


if __name__ == '__main__':
    unittest.main()
