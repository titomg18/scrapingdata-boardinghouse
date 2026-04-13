"""
Mamikos Scraper v4.1 - Fix Overlay Error
=========================================
Fix: <html> intercepts pointer events
  → Pakai JS click (bypass overlay)
  → Dismiss modal/popup sebelum klik
  → Wrap semua click dalam try-except
"""

import asyncio
import csv
import json
import time
from playwright.async_api import async_playwright

# ─── Konfigurasi ────────────────────────────────────────────────
TARGET_TOTAL        = 3000
MAX_CLICK_PER_CITY  = 150
DELAY_AFTER_CLICK   = 3.5
OUTPUT_CSV          = "mamikos_jawatimur_3000.csv"
OUTPUT_JSON         = "mamikos_jawatimur_3000.json"
HEADLESS            = True

KOTA_JATIM = [
    ("Surabaya",    "https://mamikos.com/cari/surabaya--jawa-timur--id/all/all/1-bulan"),
    ("Malang",      "https://mamikos.com/cari/malang--jawa-timur--id/all/all/1-bulan"),
    ("Jember",      "https://mamikos.com/cari/jember--jawa-timur--id/all/all/1-bulan"),
    ("Kediri",      "https://mamikos.com/cari/kediri--jawa-timur--id/all/all/1-bulan"),
    ("Blitar",      "https://mamikos.com/cari/blitar--jawa-timur--id/all/all/1-bulan"),
    ("Madiun",      "https://mamikos.com/cari/madiun--jawa-timur--id/all/all/1-bulan"),
    ("Mojokerto",   "https://mamikos.com/cari/mojokerto--jawa-timur--id/all/all/1-bulan"),
    ("Pasuruan",    "https://mamikos.com/cari/pasuruan--jawa-timur--id/all/all/1-bulan"),
    ("Probolinggo", "https://mamikos.com/cari/probolinggo--jawa-timur--id/all/all/1-bulan"),
    ("Banyuwangi",  "https://mamikos.com/cari/banyuwangi--jawa-timur--id/all/all/1-bulan"),
    ("Sidoarjo",    "https://mamikos.com/cari/sidoarjo--jawa-timur--id/all/all/1-bulan"),
    ("Gresik",      "https://mamikos.com/cari/gresik--jawa-timur--id/all/all/1-bulan"),
    ("Lumajang",    "https://mamikos.com/cari/lumajang--jawa-timur--id/all/all/1-bulan"),
    ("Jombang",     "https://mamikos.com/cari/jombang--jawa-timur--id/all/all/1-bulan"),
    ("Tulungagung", "https://mamikos.com/cari/tulungagung--jawa-timur--id/all/all/1-bulan"),
    ("Bojonegoro",  "https://mamikos.com/cari/bojonegoro--jawa-timur--id/all/all/1-bulan"),
    ("Lamongan",    "https://mamikos.com/cari/lamongan--jawa-timur--id/all/all/1-bulan"),
    ("Nganjuk",     "https://mamikos.com/cari/nganjuk--jawa-timur--id/all/all/1-bulan"),
    ("Ponorogo",    "https://mamikos.com/cari/ponorogo--jawa-timur--id/all/all/1-bulan"),
    ("Trenggalek",  "https://mamikos.com/cari/trenggalek--jawa-timur--id/all/all/1-bulan"),
]

FASILITAS_TARGET = [
    "Kasur", "AC", "WiFi", "K. Mandi Dalam", "Kloset Duduk",
    "Lemari", "Meja", "Dapur", "Parkir Motor", "Parkir Mobil",
    "Mesin Cuci", "Laundry", "Akses 24 Jam", "Air Panas",
]

KEYWORD_MAP = {
    "Kasur"         : ["kasur", "tempat tidur", "bed"],
    "AC"            : ["ac"],
    "WiFi"          : ["wifi", "wi-fi"],
    "K. Mandi Dalam": ["k. mandi dalam", "km dalam", "kamar mandi dalam"],
    "Kloset Duduk"  : ["kloset duduk"],
    "Lemari"        : ["lemari", "storage"],
    "Meja"          : ["meja"],
    "Dapur"         : ["dapur"],
    "Parkir Motor"  : ["parkir motor"],
    "Parkir Mobil"  : ["parkir mobil"],
    "Mesin Cuci"    : ["mesin cuci"],
    "Laundry"       : ["laundry"],
    "Akses 24 Jam"  : ["akses 24 jam", "24 jam"],
    "Air Panas"     : ["air panas"],
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

FIELDNAMES = ["nama_kos", "lokasi", "kota", "harga", "tipe_kos"] + FASILITAS_TARGET


# ═══════════════════════════════════════════════════════════════
#  DISMISS OVERLAY / MODAL
# ═══════════════════════════════════════════════════════════════

async def dismiss_overlays(page):
    """Tutup semua modal/popup yang menghalangi klik via JavaScript."""
    try:
        await page.evaluate("""
            const selectors = [
                '.modal.in', '.modal-backdrop', '.aside-backdrop',
                '[class*="backdrop"]', '.bg-c-modal--backdrop',
                '#loginModal', '.toasted-container',
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                    el.style.zIndex = '-9999';
                    try { el.remove(); } catch(e) {}
                });
            });
            document.body.classList.remove('modal-open');
            document.body.style.paddingRight = '';
            document.body.style.overflow = '';
            document.documentElement.style.overflow = '';
        """)
        await asyncio.sleep(0.5)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  KLIK LOAD MORE (FULL JS — BYPASS OVERLAY)
# ═══════════════════════════════════════════════════════════════

async def click_load_more(page) -> bool:
    """Klik 'Lihat lebih banyak' via JavaScript, tidak terhalangi overlay."""
    await dismiss_overlays(page)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(1)

    clicked = await page.evaluate("""
        () => {
            const selectors = [
                '.list__content-load-link',
                'a.list__content-load-link',
                '[class*="load-link"]',
                '[class*="load-more"]',
                '[class*="load-action"] a',
                '[class*="load-action"] span',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) { el.click(); return true; }
            }
            // Fallback: cari berdasarkan teks
            const els = document.querySelectorAll('a, button, span[role="button"], span');
            for (const el of els) {
                const txt = (el.textContent || '').trim().toLowerCase();
                if (txt === 'lihat lebih banyak lagi' || txt === 'lihat lebih banyak') {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """)
    return bool(clicked)


# ═══════════════════════════════════════════════════════════════
#  EXTRACT KARTU LISTING
# ═══════════════════════════════════════════════════════════════

async def extract_all_cards(page, kota_label: str) -> list[dict]:
    results = []
    cards = []
    for sel in ['[data-testid="roomCard"]', '.room-list__card', '.kost-rc']:
        try:
            cards = await page.query_selector_all(sel)
            if cards:
                break
        except Exception:
            pass

    for card in cards:
        row = {f: "Tidak" for f in FASILITAS_TARGET}
        row.update({"nama_kos": "", "lokasi": "", "kota": kota_label,
                    "harga": "", "tipe_kos": ""})

        for selector, field in [
            (".rc-info__name",                    "nama_kos"),
            (".rc-info__location",                "lokasi"),
            ("[data-testid='kostListPriceReal']", "harga"),
            (".rc-overview__label",               "tipe_kos"),
        ]:
            try:
                el = await card.query_selector(selector)
                if el:
                    row[field] = (await el.inner_text()).strip()
            except Exception:
                pass

        try:
            fac_els = await card.query_selector_all(
                "[data-testid='roomCardFacilities-facility'] span:first-child"
            )
            fac_texts = []
            for fel in fac_els:
                txt = (await fel.inner_text()).strip().lower()
                if txt and txt != "·":
                    fac_texts.append(txt)
            fac_joined = " · ".join(fac_texts)
            for fasilitas, keywords in KEYWORD_MAP.items():
                for kw in keywords:
                    if kw in fac_joined:
                        row[fasilitas] = "Ada"
                        break
        except Exception:
            pass

        if row["nama_kos"]:
            results.append(row)

    return results


def make_key(row):
    return f"{row['nama_kos']}|{row['lokasi']}"


def append_csv(rows, filepath, write_header):
    mode = "w" if write_header else "a"
    with open(filepath, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ═══════════════════════════════════════════════════════════════
#  SCRAPER PER KOTA
# ═══════════════════════════════════════════════════════════════

async def scrape_kota(page, kota_name, url, existing_keys, target_remaining):
    print(f"\n{'═'*65}")
    print(f"  🏙  {kota_name}  |  Target tersisa: {target_remaining}")
    print(f"{'═'*65}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print(f"  ❌ Gagal: {e}")
        return []

    try:
        await page.wait_for_selector(
            '[data-testid="roomCard"], .room-list__card, .kost-rc',
            timeout=25000
        )
    except Exception:
        print(f"  ⚠  Tidak ada listing di {kota_name}")
        return []

    await asyncio.sleep(2)
    await dismiss_overlays(page)
    await asyncio.sleep(1)

    new_data       = []
    click_count    = 0
    no_grow_count  = 0
    last_card_cnt  = 0

    while click_count <= MAX_CLICK_PER_CITY:
        all_cards = await extract_all_cards(page, kota_name)

        fresh = [r for r in all_cards if make_key(r) not in existing_keys]
        for r in fresh:
            existing_keys.add(make_key(r))
        new_data.extend(fresh)

        print(f"  [Klik {click_count:>3}] Kartu: {len(all_cards):>4} | "
              f"Baru: {len(fresh):>3} | Total kota: {len(new_data):>4}")

        if len(new_data) >= target_remaining:
            print(f"  ✅ Target tercapai")
            break

        # Deteksi halaman tidak berkembang
        if len(all_cards) <= last_card_cnt:
            no_grow_count += 1
            if no_grow_count >= 3:
                print(f"  🔚 Tidak ada pertumbuhan kartu, pindah kota")
                break
        else:
            no_grow_count = 0
            last_card_cnt = len(all_cards)

        success = await click_load_more(page)
        if success:
            click_count += 1
            await asyncio.sleep(DELAY_AFTER_CLICK)
        else:
            no_grow_count += 1
            print(f"  ⚠  Load more tidak ditemukan ({no_grow_count}/3)")
            if no_grow_count >= 3:
                break
            await asyncio.sleep(2)

    print(f"  📊 {kota_name}: {len(new_data)} listing")
    return new_data


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    print("\n" + "="*65)
    print("  🏠 MAMIKOS SCRAPER v4.1  |  Fix: JS Click + Dismiss Overlay")
    print("="*65)

    all_data        = []
    existing_keys   = set()
    csv_header_done = False
    t0              = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await context.new_page()
        page.set_default_timeout(15000)   # Timeout pendek → tidak hang lama

        for kota_name, url in KOTA_JATIM:
            remaining = TARGET_TOTAL - len(all_data)
            if remaining <= 0:
                print(f"\n🎉 Target {TARGET_TOTAL} tercapai!")
                break

            kota_data = await scrape_kota(
                page, kota_name, url, existing_keys, remaining
            )

            if kota_data:
                all_data.extend(kota_data)
                append_csv(kota_data, OUTPUT_CSV, write_header=not csv_header_done)
                csv_header_done = True
                elapsed = time.time() - t0
                print(f"  💾 Tersimpan | Total: {len(all_data):,} | "
                      f"Waktu: {elapsed/60:.1f} mnt")

            if len(all_data) < TARGET_TOTAL:
                await asyncio.sleep(5)

        await browser.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'='*65}")
    print(f"  ✅  SELESAI!")
    print(f"  📊  Total  : {len(all_data):,} listing")
    print(f"  ⏱   Waktu  : {elapsed/60:.1f} menit")
    print(f"  📁  CSV    : {OUTPUT_CSV}")
    print(f"  📁  JSON   : {OUTPUT_JSON}")
    print(f"{'='*65}")

    if all_data:
        kota_count = {}
        for r in all_data:
            kota_count[r["kota"]] = kota_count.get(r["kota"], 0) + 1
        print("\n  📈 Per kota:")
        for k, v in sorted(kota_count.items(), key=lambda x: -x[1]):
            print(f"     {k:<15}: {v:>5}")


if __name__ == "__main__":
    asyncio.run(main())