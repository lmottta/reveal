from app.rpa.google_web import GoogleWebRPA
from app.api.endpoints.search import clean_duplicates, get_db
from app.db.session import SessionLocal

def test_web_rpa():
    rpa = GoogleWebRPA()
    query = "8933407-11.2016.8.14.4071" 
    print(f"Testing Web RPA for {query}...")
    result = rpa.search(query)
    print("Results:", result)
    assert result["status"] == "success"
    if result["results"]:
        print(f"Found {len(result['results'])} results.")
        for res in result["results"]:
            print(f"- {res['tribunal']} | {res['origem']} | {res['assunto']}")

def test_cleanup():
    db = SessionLocal()
    print("Cleaning duplicates...")
    try:
        res = clean_duplicates(db)
        print(res)
    finally:
        db.close()

if __name__ == "__main__":
    test_web_rpa()
    # test_cleanup() # Commented out to avoid affecting real DB during simple test
