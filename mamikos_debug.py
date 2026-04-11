"""
Mamikos DEBUG Script
Tujuan: Cek struktur HTML halaman listing Mamikos
        lalu simpan screenshot + HTML untuk analisis selector
"""

import asyncio
from playwright.async_api import async_playwright

URL = "https://mamikos.com/cari/jawa-timur--id/all/all/1-bulan"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,   # Buka browser supaya kelihatan
            slow_mo=500,
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        print(f"🌐 Membuka: {URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # Tunggu lebih lama agar JS selesai render
        print("⏳ Menunggu halaman render (10 detik)...")
        await asyncio.sleep(10)

        # Scroll ke bawah agar lazy-load terpicu
        print("📜 Scroll halaman...")
        for _ in range(5):
            await page.keyboard.press("End")
            await asyncio.sleep(1)

        # ── Screenshot ──────────────────────────────────────────
        await page.screenshot(path="debug_screenshot.png", full_page=True)
        print("📸 Screenshot disimpan: debug_screenshot.png")

        # ── Simpan HTML ─────────────────────────────────────────
        html = await page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("💾 HTML disimpan: debug_page.html")

        # ── Cari semua <a> yang mengandung kata kunci ──────────
        print("\n🔍 Mencari link listing...")
        keywords = ["/kost/", "/detail/", "mamikos.com/", "/kamar/", "/room/"]
        for kw in keywords:
            links = await page.query_selector_all(f"a[href*='{kw}']")
            print(f"  '{kw}' → {len(links)} link ditemukan")
            for link in links[:3]:  # Tampilkan 3 contoh
                href = await link.get_attribute("href")
                print(f"    {href}")

        # ── Cek semua <a> di halaman ────────────────────────────
        all_links = await page.query_selector_all("a[href]")
        print(f"\n📌 Total semua <a href>: {len(all_links)}")
        print("Contoh 10 link pertama:")
        for link in all_links[:10]:
            href = await link.get_attribute("href")
            print(f"  {href}")

        # ── Cek class umum pada kartu listing ───────────────────
        print("\n🃏 Mencari kartu listing (class mengandung 'card'/'item'/'kost')...")
        for cls in ["card", "item", "kost", "room", "property", "listing"]:
            els = await page.query_selector_all(f"[class*='{cls}']")
            if els:
                sample = await els[0].get_attribute("class")
                print(f"  [class*='{cls}'] → {len(els)} elemen | class: {sample}")

        print("\n✅ Debug selesai! Cek file debug_screenshot.png dan debug_page.html")
        input("\nTekan Enter untuk tutup browser...")
        await browser.close()

asyncio.run(main())