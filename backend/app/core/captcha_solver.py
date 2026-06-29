import os
import base64
import time
import requests

# Tente importar bibliotecas de OCR, mas não falhe se não existirem
try:
    import pytesseract
    from PIL import Image
    import io
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

class CaptchaSolver:
    """
    Classe base para resolução de CAPTCHAs.
    Suporta implementações locais (OCR) e externas (2Captcha/AntiCaptcha).
    """
    
    def __init__(self, service="auto", api_key=None):
        self.service = service
        self.api_key = api_key or os.getenv("CAPTCHA_API_KEY")

    def solve_image(self, image_bytes: bytes) -> str | None:
        """
        Tenta resolver um CAPTCHA de imagem.
        Retorna o texto resolvido ou None em caso de falha.
        """
        if self.service == "2captcha":
            return self._solve_2captcha(image_bytes)
        elif self.service == "anticaptcha":
            return self._solve_anticaptcha(image_bytes)
        elif self.service == "ocr_local":
            return self._solve_local_ocr(image_bytes)
        else:
            # Auto: Prioriza OCR local.
            # Se falhar e houver chave configurada, usaria serviço externo,
            # mas conforme diretriz de usar APENAS local, focaremos no OCR.
            res = self._solve_local_ocr(image_bytes)
            if res: return res
            
            # Fallback desativado por padrão para economizar
            if self.api_key and self.service == "2captcha":
                 return self._solve_2captcha(image_bytes)
                
            return None

    def _solve_local_ocr(self, image_bytes: bytes) -> str | None:
        """
        Tentativa aprimorada usando Tesseract (se instalado).
        Aplica pré-processamento para aumentar a taxa de acerto.
        """
        if not HAS_OCR:
            print("[CaptchaSolver] OCR local não disponível (instale pytesseract e Pillow).")
            return None
            
        try:
            from PIL import ImageEnhance, ImageFilter
            
            image = Image.open(io.BytesIO(image_bytes))
            
            # 1. Converter para escala de cinza
            image = image.convert('L')
            
            # 2. Aumentar resolução (Upscaling 2x ou 3x ajuda o Tesseract)
            width, height = image.size
            image = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
            
            # 3. Aumentar contraste
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # 4. Binarização (Threshold)
            # Tentar limpar ruído de fundo
            image = image.point(lambda x: 0 if x < 140 else 255, '1')
            
            # 5. Configuração do Tesseract
            # --psm 7: Tratar como uma única linha de texto
            # -c tessedit_char_whitelist: Opcional, se soubermos que é só numérico ou alfanumérico
            custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            
            text = pytesseract.image_to_string(image, config=custom_config).strip()
            
            # Limpar caracteres não alfanuméricos (caso o whitelist falhe ou não seja usado)
            clean_text = "".join(c for c in text if c.isalnum())
            
            print(f"[CaptchaSolver] OCR Local (Processado) resolveu: {clean_text}")
            
            # Validação básica: CAPTCHAs geralmente têm 4 a 6 caracteres
            if 3 <= len(clean_text) <= 8:
                return clean_text
            else:
                print(f"[CaptchaSolver] OCR ignorado (tamanho inválido: {len(clean_text)})")
                return None
                
        except Exception as e:
            print(f"[CaptchaSolver] Erro no OCR local: {e}")
            return None

    def _solve_2captcha(self, image_bytes: bytes) -> str | None:
        """
        Implementação para 2Captcha.
        """
        if not self.api_key:
            print("[CaptchaSolver] API Key não configurada para 2Captcha.")
            return None
            
        try:
            # 1. Enviar imagem
            url_in = "http://2captcha.com/in.php"
            b64_img = base64.b64encode(image_bytes).decode('utf-8')
            payload = {
                'key': self.api_key,
                'method': 'base64',
                'body': b64_img,
                'json': 1
            }
            resp = requests.post(url_in, data=payload)
            if resp.status_code != 200: return None
            
            req_id = resp.json().get("request")
            if not req_id: return None
            
            # 2. Aguardar resolução
            url_res = "http://2captcha.com/res.php"
            for _ in range(20): # Tentar por 40-60 segundos
                time.sleep(3)
                resp_res = requests.get(f"{url_res}?key={self.api_key}&action=get&id={req_id}&json=1")
                if resp_res.status_code != 200: continue
                
                data = resp_res.json()
                if data.get("status") == 1:
                    return data.get("request")
                if data.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                    return None
                    
            return None
        except Exception as e:
            print(f"[CaptchaSolver] Erro no 2Captcha: {e}")
            return None

    def _solve_anticaptcha(self, image_bytes: bytes) -> str | None:
        # Implementação similar ao 2Captcha
        return None

# Instância global (Singleton-ish)
solver = CaptchaSolver()
