import asyncio
from playwright.async_api import async_playwright

URL = "https://www.sewakost.com/kost/jawa-timur/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Scroll
        for _ in range(3):
            await page.keyboard.press("End")
            await asyncio.sleep(1)

        # Screenshot dan HTML
        await page.screenshot(path="sewakost_debug.png", full_page=True)
        html = await page.content()
        with open("sewakost_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("✅ Screenshot & HTML disimpan. Buka sewakost_debug.html untuk analisis.")

        # Cari kartu listing
        cards = await page.query_selector_all("div[class*='kost'], div[class*='item'], .card")
        print(f"\nJumlah kartu terdeteksi (coba): {len(cards)}")

        # Cari link detail
        links = await page.query_selector_all("a[href*='/kost/']")
        print(f"Link dengan '/kost/': {len(links)}")
        for link in links[:5]:
            href = await link.get_attribute("href")
            print(f"  {href}")

        input("\nTekan Enter untuk tutup browser...")
        await browser.close()

asyncio.run(main())