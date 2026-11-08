"""End-to-end smoke test (Playwright, headless Chromium).
Run with backend on :8000 and `npm run dev` on :5173:
    ../.venv/bin/python e2e/smoke_test.py [screenshot_dir]
Walks the full user journey: landing -> 7-step wizard -> calculate -> dashboard -> what-if -> PDF download."""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e/screens")
OUT.mkdir(parents=True, exist_ok=True)
errors: list[str] = []

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    shot = lambda n, full=True: pg.screenshot(path=str(OUT / f"{n}.png"), full_page=full)  # noqa: E731

    pg.goto(BASE)
    expect(pg.get_by_role("button", name="Calculate My Conference Footprint")).to_be_visible()
    shot("01_landing")
    pg.get_by_role("button", name="Calculate My Conference Footprint").click()

    # Step 1 - basic
    pg.get_by_placeholder("e.g. National Conference on Climate Action 2027").fill("E2E Test Symposium")
    pg.locator("input[type=date]").nth(0).fill("2027-03-10")
    pg.locator("input[type=date]").nth(1).fill("2027-03-11")
    pg.get_by_label("In-person attendees").fill("150") if pg.get_by_label("In-person attendees").count() else None
    nums = pg.locator("section:has-text('Participants') input[type=number]")
    nums.nth(0).fill("150"); nums.nth(1).fill("10"); nums.nth(2).fill("8")
    shot("02_basic")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 2 of 8")

    # Step 2 - transport: one flight (IATA) + one train
    expect(pg.get_by_text("Transportation", exact=True).first).to_be_visible()
    pg.get_by_role("button", name="Flight").last.click()
    pg.get_by_label("Origin").first.fill("DEL")
    pg.get_by_label("Destination").first.fill("BLR")
    pg.locator("input[type=number]").nth(1).fill("12")  # passengers (distance empty -> airport GCD)
    pg.get_by_role("button", name="Train / metro").last.click()
    card = pg.locator("div.rounded-2xl").nth(1)
    card.get_by_placeholder("City / place").fill("Chennai")
    card.get_by_placeholder("City / venue").fill("Bengaluru")
    card.locator("input[type=number]").nth(0).fill("350")
    card.locator("input[type=number]").nth(1).fill("40")
    shot("03_transport")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 3 of 8")

    # Step 3 - accommodation
    pg.get_by_role("button", name="Add accommodation").click()
    pg.locator("input[type=number]").nth(0).fill("20")
    shot("04_accommodation")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 4 of 8")

    # Step 4 - energy
    pg.locator("input[type=number]").nth(0).fill("2500")
    pg.locator("input[type=number]").nth(3).fill("60")
    shot("05_energy")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 5 of 8")

    # Step 5 - food: lunch counts
    lunch = pg.locator("section:has(h2:text-is('Lunch'))")
    lunch.locator("input[type=number]").nth(0).fill("250")
    lunch.locator("input[type=number]").nth(2).fill("80")
    shot("06_food")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 6 of 8")

    # Step 6 - waste
    pg.get_by_role("button", name="Add waste stream").click()
    w = pg.locator("div.card").last
    w.locator("input[type=number]").nth(0).fill("60")
    w.locator("input[type=number]").nth(1).fill("20")
    shot("07_waste")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 7 of 8")

    # Step 7 - materials
    pg.get_by_role("button", name="Printed programmes / brochures").click()
    pg.locator("input[type=number]").nth(0).fill("1500")
    shot("08_materials")
    pg.get_by_role("button", name="Next").click()
    pg.wait_for_selector("text=Step 8 of 8")

    # Review
    expect(pg.get_by_text("Live preview")).to_be_visible()
    pg.wait_for_selector("text=Per participant", timeout=15000)
    shot("09_review")
    pg.get_by_role("button", name="Calculate footprint").click()

    # Dashboard
    pg.wait_for_url("**/results/*", timeout=30000)
    expect(pg.get_by_text("Total footprint")).to_be_visible()
    pg.wait_for_timeout(800)
    shot("10_dashboard")
    shot("10b_dashboard_viewport", full=False)

    # What-if
    pg.get_by_role("link", name="What-if", exact=True).click()
    pg.wait_for_selector("text=Scenario presets")
    pg.get_by_role("button", name="Run").nth(5).click()   # vegetarian meals
    pg.wait_for_selector("text=Compared with the stored baseline calculation", timeout=15000)
    pg.wait_for_timeout(600)
    shot("11_whatif")

    # Report
    pg.get_by_role("link", name="Report", exact=True).click()
    with pg.expect_download(timeout=60000) as dl:
        pg.get_by_role("button", name="Generate & download PDF").click()
    path = OUT / dl.value.suggested_filename
    dl.value.save_as(path)
    shot("12_report")

    # mobile layout
    m = ctx.new_page(); m.set_viewport_size({"width": 390, "height": 844})  # same session token
    m.goto(pg.url.replace("/report", ""))
    m.wait_for_selector("text=Total footprint")
    m.wait_for_timeout(600)
    m.screenshot(path=str(OUT / "13_mobile_dashboard.png"), full_page=False)
    b.close()

print("PDF:", path, path.stat().st_size, "bytes")
real = [e for e in errors if "favicon" not in e and "Support for defaultProps" not in e]  # known recharts 2.x dev warning
print("console errors:", real or "none")
sys.exit(1 if real else 0)
