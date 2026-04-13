import asyncio
import csv
import json
import re
from playwright.async_api import async_playwright

BASE_URL = "https://www.sewakost.com/kost/jawa-timur/"
OUTPUT_CSV = "sewakost_jatim.csv"
OUTPUT_JSON = "sewakost_jatim.json"
MAX_PAGES = 10          # maksimal halaman yang akan di-scrape
DELAY_SEC = 3

# Daftar fasilitas yang diminta (tidak tersedia di listing)
FASILITAS = [
    "Tempat Tidur",
    "Lemari Pakaian",
    "Meja",
    "Kamar Mandi Dalam",
    "AC",
    "WiFi",
    "Dapur",
    "Area Parkir",
    "Laundry Area"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Selector hasil debug dari file HTML
CARD_SELECTOR = "article.item"
NAME_SELECTOR = "a.link-large"
PRICE_SELECTOR = ".price-tag span"
LOCATION_SPAN_INDEX = 2  # span ke-3 (0-based) = kecamatan, ke-4 = kota

async def extract_cards(page) -> list[dict]:
    """Ekstrak nama, lokasi, harga dari kartu listing."""
    results = []
    try:
        await page.wait_for_selector(CARD_SELECTOR, timeout=15000)
    except:
        return results

    cards = await page.query_selector_all(CARD_SELECTOR)
    print(f"  📦 Kartu ditemukan: {len(cards)}")

    for card in cards:
        # Nama kost
        name_el = await card.query_selector(NAME_SELECTOR)
        nama = (await name_el.inner_text()).strip() if name_el else ""

        # Harga (bersihkan teks)
        price_el = await card.query_selector(PRICE_SELECTOR)
        if price_el:
            raw_price = (await price_el.inner_text()).strip()
            # Contoh: "Rp 525.000", "Hubungi", "mulai Rp 500.000"
            match = re.search(r"Rp\s*([\d\.]+)", raw_price)
            harga = f"Rp {match.group(1)}" if match else raw_price
        else:
            harga = ""

        # Lokasi: ambil span ke-3 (kecamatan) dan ke-4 (kota)
        spans = await card.query_selector_all("li.fields span")
        if len(spans) >= 4:
            kecamatan = (await spans[2].inner_text()).strip()
            kota = (await spans[3].inner_text()).strip()
            lokasi = f"{kecamatan}, {kota}"
        else:
            lokasi = ""

        if nama or harga:
            row = {"nama_kos": nama, "lokasi": lokasi, "harga": harga}
            # Isi semua fasilitas dengan "Tidak" (tidak tersedia di listing)
            for f in FASILITAS:
                row[f] = "Tidak"
            results.append(row)

    return results

async def main():
    all_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])  # ganti headless=True jika sudah yakin
        context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}index{page_num}/" if page_num > 1 else BASE_URL
            print(f"\n📄 Halaman {page_num}: {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(DELAY_SEC)

                cards_data = await extract_cards(page)
                print(f"  📊 Data: {len(cards_data)} listing")

                if not cards_data:
                    print("  🔚 Tidak ada data, berhenti.")
                    break

                for row in cards_data:
                    print(f"    ✔ {row['nama_kos'][:40]:<40} | {row['lokasi']:<30} | {row['harga']}")

                all_data.extend(cards_data)

                # Cek apakah ada tombol "Next" (pagination)
                next_btn = await page.query_selector("ul.pagination li.navigator.rs a")
                if not next_btn:
                    print("  🔚 Tidak ada halaman berikutnya.")
                    break

            except Exception as e:
                print(f"  ⚠ Error halaman {page_num}: {e}")
                break

        await browser.close()

    if all_data:
        fieldnames = ["nama_kos", "lokasi", "harga"] + FASILITAS
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Selesai! Total listing: {len(all_data)}")
        print(f"📁 CSV: {OUTPUT_CSV}\n📁 JSON: {OUTPUT_JSON}")
    else:
        print("❌ Tidak ada data yang berhasil di-scrape.")

if __name__ == "__main__":
    asyncio.run(main())