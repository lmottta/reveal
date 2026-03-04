from playwright.sync_api import sync_playwright

def test_playwright():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://example.com")
            print(page.title())
            browser.close()
            print("Playwright works!")
    except Exception as e:
        print(f"Playwright failed: {e}")

if __name__ == "__main__":
    test_playwright()
