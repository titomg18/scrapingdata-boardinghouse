# rumah123_scraper.py
import asyncio
import csv
import json
import re
import random
import os
from playwright.async_api import async_playwright

# ========== KONFIGURASI ==========
BASE_URL = "https://www.rumah123.com/kost/di-jawa-timur/"
OUTPUT_CSV = "rumah123_jatim.csv"
OUTPUT_JSON = "rumah123_jatim.json"
CHECKPOINT_FILE = "rumah123_checkpoint.json"
DELAY_LISTING = random.uniform(2, 4)      # antara 2-4 detik
DELAY_DETAIL = random.uniform(4, 7)       # antara 4-7 detik

FASILITAS = [
    "Tempat Tidur", "Lemari Pakaian", "Meja",
    "Kamar Mandi Dalam", "AC", "WiFi", "Dapur",
    "Area Parkir", "Laundry Area"
]

# Mapping keyword fasilitas (berdasarkan hasil observasi halaman detail)
KEYWORD_MAP = {
    "Tempat Tidur": ["kasur", "spring bed", "tempat tidur", "bed", "sprei"],
    "Lemari Pakaian": ["lemari", "almari", "wardrobe", "closet"],
    "Meja": ["meja", "desk", "meja belajar"],
    "Kamar Mandi Dalam": ["kamar mandi dalam", "km dalam", "bathroom inside", "kamar mandi pribadi"],
    "AC": ["ac", "air conditioner", "ac split"],
    "WiFi": ["wifi", "wi-fi", "free wifi", "internet"],
    "Dapur": ["dapur", "kitchen", "dapur bersama"],
    "Area Parkir": ["parkir", "parking", "parkir mobil", "parkir motor", "area parkir"],
    "Laundry Area": ["laundry", "mesin cuci", "area laundry"]
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# ========== SELECTOR YANG DIPERBAIKI (berdasarkan debug) ==========
# Karena tidak ada card container yang jelas, kita langsung ambil semua link ke properti
LISTING_LINK_SELECTOR = "a[href*='/properti/']"

# Untuk ekstraksi nama, harga, lokasi dari dalam atau sekitar link
# Nama biasanya ada di dalam tag h2/h3 atau atribut data-testid
NAME_SELECTOR_IN_LINK = "h2, h3, [data-testid='property-title']"

# Harga bisa berada di sibling atau parent dari link, coba beberapa kemungkinan
PRICE_SELECTOR = "[data-testid='price-value'], span[class*='price'], div[class*='price']"

# Lokasi
LOCATION_SELECTOR = "[data-testid='property-location'], div[class*='location'], span[class*='loc']"

# Pagination: tombol next
NEXT_SELECTOR = "a[rel='next'], a[aria-label='Next'], a:has-text('Selanjutnya'), a:has-text('Next')"

# ========== FUNGSI EKSTRAK ==========
def parse_harga(raw_price: str) -> str:
    """Bersihkan teks harga"""
    if not raw_price:
        return ""
    raw_price = raw_price.replace("Rp", "").replace("Total", "").strip()
    match = re.search(r"([\d\.]+)\s*(Juta|jt|ribu|rb)?", raw_price, re.IGNORECASE)
    if match:
        angka = match.group(1).replace(".", "")
        satuan = match.group(2) or ""
        if satuan.lower() in ["juta", "jt"]:
            return f"Rp {int(angka) * 1000000:,}".replace(",", ".")
        elif satuan.lower() in ["ribu", "rb"]:
            return f"Rp {int(angka) * 1000:,}".replace(",", ".")
        else:
            return f"Rp {int(angka):,}".replace(",", ".")
    return raw_price

async def extract_listing_cards(page) -> list[dict]:
    """Ambil data dasar dari kartu listing menggunakan link /properti/"""
    results = []
    # Tunggu hingga minimal satu link muncul (menandakan halaman sudah memuat listing)
    try:
        await page.wait_for_selector(LISTING_LINK_SELECTOR, timeout=15000)
    except:
        print("  ⚠ Tidak ada link properti ditemukan dalam waktu tunggu.")
        return results

    # Ambil semua link properti
    links = await page.query_selector_all(LISTING_LINK_SELECTOR)
    print(f"  🔗 Ditemukan {len(links)} link properti.")

    for link in links:
        try:
            # Ambil URL detail
            href = await link.get_attribute("href")
            if not href:
                continue
            detail_url = href if href.startswith("http") else f"https://www.rumah123.com{href}"

            # Ambil nama kost
            name_el = await link.query_selector(NAME_SELECTOR_IN_LINK)
            if name_el:
                nama = (await name_el.inner_text()).strip()
            else:
                # fallback: teks dari link itu sendiri
                nama = (await link.inner_text()).strip()
            if not nama or len(nama) < 3:
                continue

            # Cari parent container terdekat (biasanya div dengan class card/item/listing)
            parent = await link.query_selector("xpath=ancestor::div[contains(@class,'card') or contains(@class,'item') or contains(@class,'listing') or contains(@class,'property')]")

            # Ambil harga
            harga = ""
            if parent:
                price_el = await parent.query_selector(PRICE_SELECTOR)
                if price_el:
                    harga_raw = (await price_el.inner_text()).strip()
                    harga = parse_harga(harga_raw)
            if not harga:
                # coba cari di seluruh halaman terdekat dengan link (sibling)
                try:
                    price_el = await link.query_selector("xpath=following-sibling::*[self::div or self::span][contains(@class,'price')]")
                    if price_el:
                        harga_raw = (await price_el.inner_text()).strip()
                        harga = parse_harga(harga_raw)
                except:
                    pass

            # Ambil lokasi
            lokasi = ""
            if parent:
                loc_el = await parent.query_selector(LOCATION_SELECTOR)
                if loc_el:
                    lokasi = (await loc_el.inner_text()).strip()
            if not lokasi:
                # fallback: cari di sibling atau dari atribut alt gambar
                try:
                    img = await link.query_selector("img")
                    if img:
                        alt = await img.get_attribute("alt")
                        if alt and "di" in alt:
                            lokasi = alt.split("di")[-1].strip()
                except:
                    pass

            results.append({
                "nama_kos": nama,
                "lokasi": lokasi,
                "harga": harga,
                "detail_url": detail_url
            })
        except Exception as e:
            print(f"    ⚠ Error ekstrak satu listing: {e}")
            continue

    return results

async def extract_facilities(page, url: str) -> dict:
    """Ekstrak fasilitas dari halaman detail"""
    facilities = {f: "Tidak" for f in FASILITAS}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(DELAY_DETAIL)

        # Ambil semua teks dari body
        body_text = await page.inner_text("body")
        body_text_lower = body_text.lower()

        for fas, keywords in KEYWORD_MAP.items():
            for kw in keywords:
                if kw in body_text_lower:
                    facilities[fas] = "Ada"
                    break

        # Cek section fasilitas spesifik (jika ada)
        fac_section = await page.query_selector("div[data-testid='facilities-section']")
        if fac_section:
            fac_text = await fac_section.inner_text()
            fac_text_lower = fac_text.lower()
            for fas, keywords in KEYWORD_MAP.items():
                if facilities[fas] == "Tidak":
                    for kw in keywords:
                        if kw in fac_text_lower:
                            facilities[fas] = "Ada"
                            break

    except Exception as e:
        print(f"      ⚠ Gagal ekstrak fasilitas dari {url}: {e}")

    return facilities

async def save_checkpoint(processed_urls: set, all_data: list):
    """Simpan progress ke file checkpoint"""
    checkpoint = {
        "processed_urls": list(processed_urls),
        "total_data": len(all_data),
        "last_update": asyncio.get_event_loop().time()
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)

def load_checkpoint():
    """Muat checkpoint jika ada"""
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
        # Untuk debugging awal bisa set headless=False
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        current_url = BASE_URL
        page_count = 1
        total_listings = 0

        while True:
            print(f"\n📄 Halaman listing {page_count}: {current_url}")
            try:
                await page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                # Scroll ke bawah untuk memicu lazy loading (opsional)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(1)

                cards = await extract_listing_cards(page)
                if not cards:
                    print("  🔚 Tidak ada kartu, selesai.")
                    break

                print(f"  📦 Berhasil mengekstrak {len(cards)} listing dari halaman ini.")
                total_listings += len(cards)

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

                    row = {
                        "nama_kos": card["nama_kos"],
                        "lokasi": card["lokasi"],
                        "harga": card["harga"],
                        "detail_url": detail_url
                    }
                    row.update(facilities)
                    all_data.append(row)
                    processed_urls.add(detail_url)

                    if len(processed_urls) % 10 == 0:
                        await save_checkpoint(processed_urls, all_data)

                # Cek tombol Next (pagination)
                next_btn = await page.query_selector(NEXT_SELECTOR)
                if not next_btn:
                    print("  🔚 Tombol Next tidak ditemukan, selesai.")
                    break

                # Ambil URL halaman berikutnya
                next_href = await next_btn.get_attribute("href")
                if not next_href:
                    # Mungkin tombol next tidak memiliki href, coba klik
                    if await next_btn.is_enabled():
                        await next_btn.click()
                        await page.wait_for_load_state("networkidle")
                        current_url = page.url
                        page_count += 1
                        continue
                    else:
                        break
                current_url = next_href if next_href.startswith("http") else f"https://www.rumah123.com{next_href}"
                page_count += 1

            except Exception as e:
                print(f"  ⚠ Error pada halaman {page_count}: {e}")
                break

        await browser.close()

    if all_data:
        fieldnames = ["nama_kos", "lokasi", "harga", "detail_url"] + FASILITAS
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Selesai! Total listing baru: {len(all_data)}")
        print(f"📁 CSV: {OUTPUT_CSV}\n📁 JSON: {OUTPUT_JSON}")
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            print("🧹 Checkpoint dihapus.")
    else:
        print("❌ Tidak ada data baru.")

if __name__ == "__main__":
    asyncio.run(main())