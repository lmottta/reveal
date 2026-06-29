# Specs — Reveal (JuriPopular)

## Stack

| Camada      | Tecnologia                                    |
|-------------|-----------------------------------------------|
| Backend     | Python 3.10+, FastAPI, Uvicorn                |
| ORM         | SQLAlchemy 2.0 + psycopg2-binary              |
| Banco       | PostgreSQL 15 (Docker) / SQLite (fallback)    |
| RPA         | Playwright + BeautifulSoup4 + lxml            |
| CAPTCHA     | Tesseract OCR + 2Captcha (opcional)           |
| Frontend    | HTML5, CSS3 vars, JS ES6+, Leaflet.js CDN     |
| Mapas       | Leaflet 1.9.4 + CartoDB dark tiles            |
| Deploy      | Docker / Railway / Vercel                     |

## Dependências

```
fastapi, uvicorn[standard], sqlalchemy>=2.0
pydantic>=2.0, pydantic-settings>=2.0
python-dotenv, requests, httpx, python-multipart
playwright, beautifulsoup4, lxml
psycopg2-binary, pytesseract, Pillow
duckduckgo_search
```

## Endpoints (`/api/v1`)

### Search
- `GET /search/?query=&state=&page=&per_page=`
- `GET /search/catalog/?state=&page=&per_page=`
- `GET /search/analyze/?id=`
- `DELETE /search/clean`
- `DELETE /search/clean/news`
- `POST /search/scan`

### Stats
- `GET /stats/kpi/?state=`
- `GET /stats/geo/?state=`
- `GET /stats/ufs/{uf}/cities/`

### Health
- `GET /health`
- `GET /diagnostics`

## Modelos (SQLAlchemy → PostgreSQL)

### Lawsuit
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | SERIAL PK | |
| cnj | VARCHAR(25) UNIQUE | Número CNJ |
| tribunal | VARCHAR(10) | TJSP, TJRJ... |
| state | VARCHAR(2) | UF |
| comarca | VARCHAR(100) | |
| court | VARCHAR(100) | Vara |
| judge | VARCHAR(200) | Juiz |
| class_type | VARCHAR(100) | Classe processual |
| subject | VARCHAR(200) | Assunto |
| parties | TEXT | JSON das partes |
| status | VARCHAR(100) | Situação |
| distribution_date | VARCHAR(20) | |
| last_movement_date | VARCHAR(20) | |
| movements | TEXT | JSON das movimentações |
| created_at | TIMESTAMPTZ | |

### News
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | SERIAL PK | |
| search_id | INTEGER FK→search | |
| title | VARCHAR(500) | |
| url | VARCHAR(1000) UNIQUE | |
| source | VARCHAR(200) | Veículo |
| author | VARCHAR(200) | |
| snippet | TEXT | |
| image_url | VARCHAR(500) | |
| published_date | VARCHAR(50) | |
| city | VARCHAR(100) | |
| state | VARCHAR(2) | |
| correlation | VARCHAR(100) | Link com processo |
| created_at | TIMESTAMPTZ | |

### Search / SearchResult
Tabelas auxiliares para log de buscas e cache de resultados.

## Keywords (Crimes Sexuais)
ESTUPRO, ABUSO SEXUAL, PEDOFILIA, TRÁFICO SEXUAL, EXPLORAÇÃO SEXUAL, VIOLÊNCIA SEXUAL, ASSÉDIO SEXUAL, IMPORTUNAÇÃO SEXUAL, CORRUPÇÃO DE MENORES, SATISFAÇÃO DE LASCÍVIA, ATO LIBIDINOSO, CRIANÇA, ADOLESCENTE, MENOR, VULNERÁVEL, STALKING, PORNOGRAFIA, ALICIAMENTO, SEXTING, VIOLAÇÃO, REGISTRO NÃO AUTORIZADO, DIVULGAÇÃO DE CENA

## Mapeamento Tribunal → RPA

| Código | Tribunal | Sistema |
|--------|----------|---------|
| 01-03 | TJAC, TJAL, TJAM | esaj |
| 04 | TJAP | tucujuris |
| 05 | TJBA | pje |
| 06 | TJCE | esaj |
| 07 | TJDF | pje |
| 08 | TJES | pje |
| 09 | TJGO | projudi |
| 10 | TJMA | pje |
| 11 | TJMT | pje |
| 12 | TJMS | esaj |
| 13 | TJMG | pje |
| 14 | TJPA | pje |
| 15 | TJPB | pje |
| 16 | TJPR | projudi |
| 17 | TJPE | pje |
| 18 | TJPI | pje |
| 19 | TJRN | pje |
| 20 | TJRS | eproc |
| 21 | TJRO | pje |
| 22 | TJRR | projudi |
| 23 | TJSC | eproc |
| 24 | TJSP | esaj |
| 25 | TJSE | pje |
| 26 | TJTO | eproc |
| 27 | TJRJ | tjrj (custom) |

## Roadmap
- [x] MVP: busca + notícias
- [x] PostgreSQL Docker
- [x] Deduplicação 3 níveis
- [x] Coleta em massa
- [ ] Exportação PDF/CSV
- [ ] Alertas de monitoramento
- [ ] Tribunais Federais (TRF)
- [ ] Grafo de relacionamentos
