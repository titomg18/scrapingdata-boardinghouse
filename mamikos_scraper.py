"""
Mamikos Scraper v3 - Jawa Timur
Strategi: Extract langsung dari kartu listing (lebih cepat & stabil)
Selector dari HTML nyata:
  - Nama  : .rc-info__name
  - Lokasi: .rc-info__location
  - Harga : [data-testid="kostListPriceReal"]
  - Fasil : [data-testid="roomCardFacilities-facility"]
"""

import asyncio
import csv
import json
from playwright.async_api import async_playwright

# ─── Konfigurasi ────────────────────────────────────────────────
# Coba beberapa format URL Jawa Timur
URLS_TO_TRY = [
    "https://mamikos.com/cari/jawa-timur--id/all/all/1-bulan",
    "https://mamikos.com/cari/jawa-timur/all/all/1-bulan",
    "https://mamikos.com/cari/surabaya--jawa-timur--id/all/all/1-bulan",
]
BASE_URL     = URLS_TO_TRY[0]   # akan dicoba satu per satu
OUTPUT_CSV   = "mamikos_jawatimur.csv"
OUTPUT_JSON  = "mamikos_jawatimur.json"
MAX_PAGES    = 10
DELAY_SEC    = 4
# ────────────────────────────────────────────────────────────────

FASILITAS_TARGET = [
    "Tempat Tidur",
    "Lemari Pakaian",
    "Meja",
    "Kamar Mandi Dalam",
    "AC",
    "WiFi",
    "Dapur",
    "Area Parkir",
    "Laundry Area",
]

# Kata kunci fasilitas di kartu Mamikos (dari HTML asli)
KEYWORD_MAP = {
    "Tempat Tidur"     : ["kasur", "tempat tidur", "bed"],
    "Lemari Pakaian"   : ["lemari", "storage", "wardrobe"],
    "Meja"             : ["meja"],
    "Kamar Mandi Dalam": ["k. mandi dalam", "km dalam", "kamar mandi dalam"],
    "AC"               : ["ac"],
    "WiFi"             : ["wifi", "wi-fi"],
    "Dapur"            : ["dapur", "kitchen"],
    "Area Parkir"      : ["parkir mobil", "parkir motor", "parkir"],
    "Laundry Area"     : ["laundry", "mesin cuci"],
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


async def wait_scroll(page, delay=4):
    await asyncio.sleep(delay)
    for _ in range(5):
        await page.keyboard.press("End")
        await asyncio.sleep(0.7)
    await asyncio.sleep(1.5)


async def extract_cards(page) -> list[dict]:
    """Extract semua data dari kartu listing di halaman saat ini."""
    results = []
    try:
        await page.wait_for_selector(".room-list__card", timeout=20000)
    except Exception as e:
        print(f"  ⚠ Tidak ada kartu: {e}")
        return results

    cards = await page.query_selector_all(".room-list__card")
    print(f"  📦 Kartu ditemukan: {len(cards)}")

    for card in cards:
        row = {"nama_kos": "", "lokasi": "", "harga": ""}
        for f in FASILITAS_TARGET:
            row[f] = "Tidak"

        # ── Nama kos ──────────────────────────────────────────
        try:
            el = await card.query_selector(".rc-info__name")
            if el:
                row["nama_kos"] = (await el.inner_text()).strip()
        except Exception:
            pass

        # ── Lokasi ────────────────────────────────────────────
        try:
            el = await card.query_selector(".rc-info__location")
            if el:
                row["lokasi"] = (await el.inner_text()).strip()
        except Exception:
            pass

        # ── Harga ─────────────────────────────────────────────
        try:
            el = await card.query_selector("[data-testid='kostListPriceReal']")
            if el:
                row["harga"] = (await el.inner_text()).strip()
        except Exception:
            pass

        # ── Fasilitas ─────────────────────────────────────────
        try:
            fac_els = await card.query_selector_all(
                "[data-testid='roomCardFacilities-facility'] span:first-child"
            )
            fac_texts = []
            for fel in fac_els:
                txt = (await fel.inner_text()).strip().lower()
                if txt:
                    fac_texts.append(txt)

            fac_joined = " · ".join(fac_texts)

            for fasilitas, keywords in KEYWORD_MAP.items():
                for kw in keywords:
                    if kw in fac_joined:
                        row[fasilitas] = "Ada"
                        break
        except Exception:
            pass

        if row["nama_kos"] or row["harga"]:   # simpan hanya jika ada data
            results.append(row)

    return results


async def find_working_url(page) -> str | None:
    """Coba URL sampai menemukan yang menampilkan listing Jawa Timur."""
    for url in URLS_TO_TRY:
        print(f"  🔍 Mencoba URL: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            title = await page.title()
            body  = await page.inner_text("body")
            print(f"     Judul halaman: {title[:70]}")

            # Cek apakah ada kartu listing
            cards = await page.query_selector_all(".room-list__card")
            if cards:
                print(f"     ✅ Berhasil! {len(cards)} kartu ditemukan")
                return url
            else:
                print(f"     ❌ Tidak ada kartu")
        except Exception as e:
            print(f"     ❌ Error: {e}")
    return None


async def main():
    all_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        # ── Cari URL yang bekerja ──────────────────────────────
        print("\n🔎 Mencari URL Jawa Timur yang valid...")
        working_url = await find_working_url(page)

        if not working_url:
            print("\n❌ Semua URL gagal. Coba buka browser manual dan cek URL Jawa Timur di mamikos.com")
            await browser.close()
            return

        # ── Scraping per halaman ───────────────────────────────
        for page_num in range(1, MAX_PAGES + 1):
            if page_num == 1:
                url = working_url
            else:
                url = f"{working_url}?page={page_num}"

            print(f"\n{'='*60}")
            print(f"📄 Halaman {page_num}/{MAX_PAGES}: {url}")
            print(f"{'='*60}")

            try:
                if page_num > 1:
                    await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await wait_scroll(page, DELAY_SEC)

                cards_data = await extract_cards(page)
                print(f"  📊 Data berhasil diambil: {len(cards_data)} listing")

                if not cards_data:
                    print("  🔚 Tidak ada data, berhenti.")
                    break

                for row in cards_data:
                    print(f"    ✔ {row['nama_kos'][:45]:<45} | {row['lokasi']:<25} | {row['harga']}")
                    ada = [f for f in FASILITAS_TARGET if row[f] == "Ada"]
                    if ada:
                        print(f"      Fasilitas: {', '.join(ada)}")

                all_data.extend(cards_data)

            except Exception as e:
                print(f"  ⚠ Error halaman {page_num}: {e}")
                break

            # Cek tombol "Lihat lebih banyak" untuk infinite scroll
            try:
                load_more = await page.query_selector(".list__content-load-link")
                if load_more and page_num < MAX_PAGES:
                    print("  🔄 Klik 'Lihat lebih banyak'...")
                    await load_more.click()
                    await asyncio.sleep(3)
                    extra = await extract_cards(page)
                    # hindari duplikat
                    existing = {d["nama_kos"] for d in all_data}
                    new_data = [d for d in extra if d["nama_kos"] not in existing]
                    all_data.extend(new_data)
                    print(f"  ➕ Tambahan: {len(new_data)} listing baru")
            except Exception:
                pass

        await browser.close()

    # ── Simpan Output ──────────────────────────────────────────
    if all_data:
        fieldnames = ["nama_kos", "lokasi", "harga"] + FASILITAS_TARGET

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ Selesai! Total listing: {len(all_data)}")
        print(f"📁 CSV  → {OUTPUT_CSV}")
        print(f"📁 JSON → {OUTPUT_JSON}")
        print(f"{'='*60}")
    else:
        print("\n❌ Tidak ada data yang berhasil di-scrape.")


if __name__ == "__main__":
    asyncio.run(main())