# sewakost_scraper_detailed_unlimited.py
import asyncio
import csv
import json
import re
import random
import os
from playwright.async_api import async_playwright

# ========== KONFIGURASI ==========
BASE_URL = "https://www.sewakost.com/kost/jawa-timur/"
OUTPUT_CSV = "sewakost_jatim_detailed.csv"
OUTPUT_JSON = "sewakost_jatim_detailed.json"
CHECKPOINT_FILE = "sewakost_checkpoint.json"  # menyimpan link yang sudah diproses
DELAY_LISTING = random.uniform(2, 4)           # antar halaman listing
DELAY_DETAIL = random.uniform(3, 6)            # antar halaman detail
MAX_RETRIES = 3                                # percobaan ulang jika gagal

FASILITAS = [
    "Tempat Tidur", "Lemari Pakaian", "Meja",
    "Kamar Mandi Dalam", "AC", "WiFi", "Dapur",
    "Area Parkir", "Laundry Area"
]

# Pemetaan keyword fasilitas (dari teks di halaman detail)
KEYWORD_MAP = {
    "Tempat Tidur": ["kasur", "spring bed", "tempat tidur", "bed"],
    "Lemari Pakaian": ["lemari", "almari", "wardrobe", "closet"],
    "Meja": ["meja", "desk", "meja lipat", "meja belajar"],
    "Kamar Mandi Dalam": ["kamar mandi dalam", "km dalam", "bathroom inside", "kamar mandi pribadi"],
    "AC": ["ac", "air conditioner", "ac split"],
    "WiFi": ["wifi", "wi-fi", "free wifi", "internet"],
    "Dapur": ["dapur", "kitchen", "dapur bersama"],
    "Area Parkir": ["parkir", "parking", "parkir mobil", "parkir motor", "area parkir"],
    "Laundry Area": ["laundry", "mesin cuci", "area laundry"]
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Selector
CARD_SELECTOR = "article.item"
NAME_SELECTOR = "a.link-large"
PRICE_SELECTOR = ".price-tag span"
NEXT_SELECTOR = "ul.pagination li.navigator.rs a"
DETAIL_URL_SELECTOR = "a.link-large"  # di kartu, ambil href

# ========== FUNGSI EKSTRAK ==========

def parse_harga(raw_price: str) -> str:
    """Bersihkan teks harga, ambil angka dengan Rp."""
    match = re.search(r"Rp\s*([\d\.]+)", raw_price)
    if match:
        return f"Rp {match.group(1)}"
    return raw_price

async def extract_listing_cards(page) -> list[dict]:
    """Ambil data dasar + URL detail dari kartu listing."""
    results = []
    cards = await page.query_selector_all(CARD_SELECTOR)
    for card in cards:
        # Nama
        name_el = await card.query_selector(NAME_SELECTOR)
        nama = (await name_el.inner_text()).strip() if name_el else ""

        # URL detail
        url_el = await card.query_selector(DETAIL_URL_SELECTOR)
        detail_url = ""
        if url_el:
            href = await url_el.get_attribute("href")
            if href:
                detail_url = href if href.startswith("http") else f"https://www.sewakost.com{href}"

        # Harga
        price_el = await card.query_selector(PRICE_SELECTOR)
        harga = ""
        if price_el:
            raw = (await price_el.inner_text()).strip()
            harga = parse_harga(raw)

        # Lokasi (kecamatan, kota)
        spans = await card.query_selector_all("li.fields span")
        lokasi = ""
        if len(spans) >= 4:
            kec = (await spans[2].inner_text()).strip()
            kota = (await spans[3].inner_text()).strip()
            lokasi = f"{kec}, {kota}"

        if nama or harga:
            results.append({
                "nama_kos": nama,
                "lokasi": lokasi,
                "harga": harga,
                "detail_url": detail_url
            })
    return results

async def extract_facilities(page, url: str) -> dict:
    """Buka halaman detail dan ekstrak fasilitas berdasarkan keyword."""
    facilities = {f: "Tidak" for f in FASILITAS}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(DELAY_DETAIL)

        # Cari semua teks yang mungkin berisi fasilitas
        # Biasanya di dalam div dengan class "facilities", "deskripsi", atau body
        # Kita ambil semua teks dari halaman (lebih mudah)
        body_text = await page.inner_text("body")
        body_text_lower = body_text.lower()

        for fas, keywords in KEYWORD_MAP.items():
            for kw in keywords:
                if kw in body_text_lower:
                    facilities[fas] = "Ada"
                    break

        # Khusus untuk AC, periksa juga filter di listing (opsional)
        # Tapi karena kita sudah baca body, itu sudah cukup.

    except Exception as e:
        print(f"      ⚠ Gagal ekstrak fasilitas dari {url}: {e}")

    return facilities

async def save_checkpoint(processed_urls: set, all_data: list):
    """Simpan progress (URL yang sudah diproses) ke file."""
    checkpoint = {
        "processed_urls": list(processed_urls),
        "total_data": len(all_data),
        "last_update": asyncio.get_event_loop().time()
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)

def load_checkpoint():
    """Muat checkpoint jika ada."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("processed_urls", []))
    return set()

# ========== MAIN ==========

async def main():
    all_data = []
    processed_urls = load_checkpoint()
    print(f"📌 Memuat checkpoint: {len(processed_urls)} URL sudah diproses.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        page_num = 1
        while True:
            url = f"{BASE_URL}index{page_num}/" if page_num > 1 else BASE_URL
            print(f"\n📄 Halaman listing {page_num}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(DELAY_LISTING)

                cards = await extract_listing_cards(page)
                if not cards:
                    print("  🔚 Tidak ada kartu, selesai.")
                    break

                print(f"  📦 Ditemukan {len(cards)} listing di halaman ini.")

                # Proses setiap kartu (ambil detail)
                for idx, card in enumerate(cards, 1):
                    detail_url = card["detail_url"]
                    if not detail_url:
                        print(f"    ⚠ Tidak ada URL detail untuk {card['nama_kos'][:40]}, lewati.")
                        continue

                    if detail_url in processed_urls:
                        print(f"    ⏩ Lewati (sudah diproses): {card['nama_kos'][:40]}")
                        continue

                    print(f"    🔍 [{idx}/{len(cards)}] Membuka detail: {card['nama_kos'][:40]} ...")
                    facilities = await extract_facilities(page, detail_url)

                    # Gabungkan data
                    row = {
                        "nama_kos": card["nama_kos"],
                        "lokasi": card["lokasi"],
                        "harga": card["harga"],
                        "detail_url": detail_url
                    }
                    row.update(facilities)
                    all_data.append(row)

                    processed_urls.add(detail_url)

                    # Simpan checkpoint setiap 10 item (atau bisa setiap item)
                    if len(processed_urls) % 10 == 0:
                        await save_checkpoint(processed_urls, all_data)

                # Cek tombol Next
                next_btn = await page.query_selector(NEXT_SELECTOR)
                if not next_btn:
                    print("  🔚 Tombol Next tidak ditemukan, selesai.")
                    break

                page_num += 1

            except Exception as e:
                print(f"  ⚠ Error pada halaman {page_num}: {e}")
                break

        await browser.close()

    # Simpan final
    if all_data:
        fieldnames = ["nama_kos", "lokasi", "harga", "detail_url"] + FASILITAS
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Selesai! Total listing: {len(all_data)}")
        print(f"📁 CSV: {OUTPUT_CSV}\n📁 JSON: {OUTPUT_JSON}")

        # Hapus checkpoint jika sukses semua
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            print("🧹 Checkpoint dihapus.")
    else:
        print("❌ Tidak ada data baru.")

if __name__ == "__main__":
    asyncio.run(main())