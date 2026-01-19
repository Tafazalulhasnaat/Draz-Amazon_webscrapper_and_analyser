import asyncio
import os
from playwright.async_api import async_playwright, TimeoutError
from database import Database
import random

# --- Helper to get absolute path to key ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

async def extract_price(product):
    try:
        # Search for price text usually starting with Rs.
        price_locator = product.locator("xpath=.//span[contains(text(), 'Rs.')]")
        if await price_locator.count() > 0:
            return (await price_locator.first.inner_text()).strip()
    except Exception as e:
        print(f"Error extracting price: {e}")
    return None

async def scrape_daraz_async(query: str):
    print(f"--- Starting Daraz Scraper for: {query} ---")
    
    # --- UPDATE: Pass the credential path here ---
    try:
        db = Database(CRED_PATH)
    except Exception as e:
        print(f"Database Init Failed: {e}")
        return

    search_url = f"https://www.daraz.pk/catalog/?q={query.replace(' ', '+')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        page = await context.new_page()

        try:
            await page.goto(
                search_url,
                timeout=60000,
                wait_until="domcontentloaded"
            )

            # Wait for products to load
            try:
                await page.wait_for_selector("div[data-qa-locator='product-item']", timeout=10000)
            except TimeoutError:
                pass

            # Fallback selectors
            products = page.locator("div[data-qa-locator='product-item']")
            if await products.count() == 0:
                products = page.locator("div.gridItem--Yd0sa")

            count = await products.count()
            limit = min(count, 10)

            saved = 0
            for i in range(limit):
                product = products.nth(i)
                try:
                    await product.scroll_into_view_if_needed()
                    await page.wait_for_timeout(random.randint(500, 1000))

                    # Extract Title
                    title_locator = product.locator("img")
                    title = (
                        await title_locator.first.get_attribute("alt")
                        if await title_locator.count() > 0
                        else "No Title"
                    )

                    # Extract Link
                    link_locator = product.locator("a")
                    url_raw = (
                        await link_locator.first.get_attribute("href")
                        if await link_locator.count() > 0
                        else None
                    )
                    full_url = f"https:{url_raw}" if url_raw and url_raw.startswith("//") else url_raw

                    # Extract Price
                    price = await extract_price(product)

                    if title and price:
                        # Database expects: (title, price, rating, retailer, url)
                        # We pass None for rating as Daraz list view often hides it
                        db.insert((title, price, None, "Daraz", full_url))
                        saved += 1

                except Exception:
                    continue

            print(f"Total saved from Daraz: {saved}")

        except Exception as e:
            print(f"Daraz Error: {e}")

        finally:
            await browser.close()
            # db.close() is just a 'pass' in Firestore, but good practice to keep
            db.close()

# 🔁 Sync wrapper (Streamlit-safe)
def scrape_daraz(query: str):
    asyncio.run(scrape_daraz_async(query))
