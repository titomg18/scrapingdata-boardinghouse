import asyncio
from playwright.async_api import async_playwright

URL = "https://www.rumah123.com/kost/di-jawa-timur/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()
        
        print(f"🌐 Membuka: {URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # tunggu render

        # Scroll
        for _ in range(3):
            await page.keyboard.press("End")
            await asyncio.sleep(1)

        # Screenshot
        await page.screenshot(path="debug_rumah123.png", full_page=True)
        print("📸 Screenshot disimpan: debug_rumah123.png")

        # Simpan HTML
        html = await page.content()
        with open("debug_rumah123.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("💾 HTML disimpan: debug_rumah123.html")

        # Cari semua kartu listing (coba berbagai selector)
        print("\n🔍 Mencari selector kartu listing...")
        possible_selectors = [
            "div[data-testid='property-card']",
            "div[class*='card']",
            "div[class*='property']",
            "a[href*='/properti/']",
            "div[class*='listing']",
            "div[class*='item']",
            "article",
            "div[data-cy='search-card']"
        ]
        for sel in possible_selectors:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"  {sel} → {count} elemen")
                # ambil contoh class
                first = await page.query_selector(sel)
                if first:
                    class_name = await first.get_attribute("class")
                    print(f"      Contoh class: {class_name}")

        # Cari link dengan pola detail kost
        links = await page.query_selector_all("a[href*='/properti/']")
        print(f"\n🔗 Link dengan '/properti/': {len(links)}")
        for link in links[:5]:
            href = await link.get_attribute("href")
            print(f"  {href}")

        input("\nTekan Enter untuk tutup browser...")
        await browser.close()

asyncio.run(main())