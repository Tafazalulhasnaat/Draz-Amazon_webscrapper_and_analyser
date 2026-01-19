import asyncio
import random
import os
from playwright.async_api import async_playwright, TimeoutError
from database import Database

async def safe_text(locator):
    try:
        if await locator.count() > 0:
            return (await locator.first.inner_text(timeout=3000)).strip()
    except TimeoutError:
        return None
    return None

async def safe_attr(locator, attr):
    try:
        if await locator.count() > 0:
            return await locator.first.get_attribute(attr, timeout=3000)
    except TimeoutError:
        return None
    return None

async def scrape_amazon_async(query: str):
    print(f"--- Starting Amazon Scraper for: {query} ---")

    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CRED_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

    # 2. FIX: Initialize Database with the path
    try:
        db = Database(CRED_PATH)
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return

    # Search URL construction
    search_url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US"
        )

        page = await context.new_page()

        try:
            await page.goto(search_url, timeout=60000)
            # Add a small random wait to mimic human behavior
            await page.wait_for_timeout(random.randint(2000, 3000))

            # Locate product cards
            products = page.locator('div[data-component-type="s-search-result"]')
            
            # Fallback if the standard selector fails (sometimes Amazon changes containers)
            if await products.count() == 0:
                 products = page.locator('.s-result-item[data-component-type="s-search-result"]')

            count = await products.count()
            limit = min(count, 10)

            saved = 0
            for i in range(limit):
                product = products.nth(i)

                title = await safe_text(product.locator("h2 span"))
                
                price = await safe_text(product.locator("span.a-price > span.a-offscreen"))
                
                rating = await safe_text(product.locator("span.a-icon-alt"))
                
                relative_url = None
                
                relative_url = await safe_attr(product.locator("h2 a"), "href")
                
                if not relative_url:
                    relative_url = await safe_attr(product.locator(".s-product-image-container a"), "href")

                if not relative_url:
                    relative_url = await safe_attr(product.locator("a"), "href")

                full_url = None
                if relative_url:
                    if relative_url.startswith("http"):
                        full_url = relative_url
                    else:
                        full_url = f"https://www.amazon.com{relative_url}"

                if title and price:
                    db.insert((title, price, rating, "Amazon", full_url))
                    saved += 1

            print(f"Total saved from Amazon: {saved}")

        except Exception as e:
            print(f"Amazon Error: {e}")

        finally:
            await browser.close()
            try:
                db.close()
            except:
                pass

def scrape_amazon(query: str):
    asyncio.run(scrape_amazon_async(query))

