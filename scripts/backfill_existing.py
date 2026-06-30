import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

from app.db.session import SessionLocal
from app.models.search import News
from app.utils.enricher import enrich_news_item, extract_real_url, clean_text

def backfill_news():
    db = SessionLocal()
    total = db.query(News).count()
    updated_url = 0
    updated_thumb = 0
    updated_text = 0

    batch = db.query(News).order_by(News.id.desc()).limit(500).all()
    print(f"Processing {len(batch)} of {total} total records")

    for n in batch:
        item = {"url": n.url, "title": n.title, "snippet": n.snippet, "source": n.source, "image_url": n.image_url}
        enriched = enrich_news_item(item)
        changed = False

        real_url = enriched.get("url", "")
        if real_url and real_url != n.url:
            n.url = real_url
            updated_url += 1
            changed = True

        thumb = enriched.get("image_url", "")
        if thumb and thumb != n.image_url:
            n.image_url = thumb
            updated_thumb += 1
            changed = True

        clean_title = clean_text(n.title)
        if clean_title != n.title:
            n.title = clean_title
            updated_text += 1
            changed = True

        clean_snippet = clean_text(n.snippet)
        if clean_snippet != n.snippet:
            n.snippet = clean_snippet
            changed = True

        if changed:
            db.commit()

    print(f" URLs corrigidas: {updated_url}")
    print(f" Thumbs adicionadas: {updated_thumb}")
    print(f" Textos limpos: {updated_text}")
    db.close()

if __name__ == "__main__":
    backfill_news()
