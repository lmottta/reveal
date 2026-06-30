import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

from app.db.session import SessionLocal
from app.models.search import News
from app.utils.enricher import enrich_news_item

def backfill():
    db = SessionLocal()
    total = db.query(News).count()
    updated = 0
    news_list = db.query(News).filter(
        (News.image_url == None) | (News.image_url == "")
    ).order_by(News.id.desc()).limit(200).all()
    print(f"Found {len(news_list)} items without thumbnails out of {total} total")
    for n in news_list:
        item = enrich_news_item({
            "url": n.url,
            "title": n.title,
            "snippet": n.snippet,
            "source": n.source,
            "image_url": n.image_url,
        })
        if item.get("image_url") and item["image_url"] != n.image_url:
            n.image_url = item["image_url"]
            db.commit()
            updated += 1
            print(f"  + Thumb for #{n.id}: {n.source}")
    print(f"Updated {updated} items with thumbnails")
    db.close()

if __name__ == "__main__":
    backfill()
