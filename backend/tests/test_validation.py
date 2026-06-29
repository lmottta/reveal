import unittest
import sys
import os

# Adicionar diretório pai ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.utils import validate_cnj

class TestCNJValidation(unittest.TestCase):
    def test_valid_cnj(self):
        # Base: 000000120248260000 -> Resto 50 -> DV 98-50 = 48
        cnj = "0000001-48.2024.8.26.0000"
        self.assertTrue(validate_cnj(cnj), f"CNJ {cnj} deveria ser válido")

        # Base: 500179920248240000 -> Resto 85 -> DV 98-85 = 13
        cnj2 = "5001799-13.2024.8.24.0000"
        self.assertTrue(validate_cnj(cnj2), f"CNJ {cnj2} deveria ser válido")

    def test_invalid_cnj(self):
        # Dígito verificador errado (correto seria 48)
        cnj = "0000001-99.2024.8.26.0000"
        self.assertFalse(validate_cnj(cnj), f"CNJ {cnj} deveria ser inválido")
        
        # Tamanho errado
        self.assertFalse(validate_cnj("123"), "CNJ curto deveria ser inválido")
        
        # Formato inválido
        self.assertFalse(validate_cnj("abcdefg"), "CNJ não numérico inválido")

if __name__ == '__main__':
    unittest.main()
