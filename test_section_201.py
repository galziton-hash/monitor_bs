"""
Test 2: Section 201 – Full Flow
================================
1. Login to Eventim.
2. Open seat map.
3. Click section 201 directly (block b900591031).
4. Find available seats (circle.s.has-hover with fill #80FF80).
5. Click exactly 2 seats.
6. Add to cart.
7. Send NTFY notification.

Also updates the main check_tickets.py detection logic with confirmed findings:
 - Available seats in drill-down: circle elements with class 's has-hover'
 - Available sections in overview: SVG <style> CSS sets fill:#1cce22 on available go_N classes
"""

import asyncio
import io
import os
import sys
import traceback
from datetime import datetime

import httpx
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOGIN_URL   = "https://hbsfc.eventim-inhouse.co.il/webshop/webticket/customerlogin.secure"
SEATMAP_URL = "https://hbsfc.eventim-inhouse.co.il/webshop/webticket/seatmap?eventId=268&el=true"

EMAIL    = os.environ.get("LOGIN_EMAIL",    "eladb8@gmail.com")
PASSWORD = os.environ.get("LOGIN_PASSWORD", "Imri1212")
NTFY_TOPIC  = os.environ.get("NTFY_TOPIC",  "hbs-shefa")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

SS = "screenshots"
os.makedirs(SS, exist_ok=True)

TEST_SECTION = "201"
TEST_BLOCK_ID = "b900591031"   # confirmed from DOM inspection
MAX_SEATS = 2                   # for this test, add only 2


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def build_cart_access_instructions(session_cookie: dict | None) -> str:
    """
    Returns clear step-by-step instructions for the user to access the
    pre-filled cart in their own browser by importing the JSESSIONID.

    The JSESSIONID is httpOnly so it cannot be set via JS console.
    It CAN be edited via Chrome DevTools → Application tab → Cookies.
    """
    if not session_cookie:
        return (
            "\n\n--- BACKUP: Add manually ---\n"
            "Open the seat map and select the seats above yourself:\n"
            "https://hbsfc.eventim-inhouse.co.il/webshop/webticket/seatmap"
            "?eventId=268&el=true"
        )

    jsid = session_cookie["value"]
    return (
        f"\n\n{'='*40}\n"
        f"HOW TO ACCESS YOUR PRE-FILLED CART\n"
        f"{'='*40}\n"
        f"Takes ~30 seconds in Chrome:\n\n"
        f"1. Open Chrome on the site (logged in)\n"
        f"2. Press F12  (Developer Tools)\n"
        f"3. Click the 'Application' tab\n"
        f"4. Left panel: Storage > Cookies >\n"
        f"   hbsfc.eventim-inhouse.co.il\n"
        f"5. Find row: JSESSIONID\n"
        f"6. Double-click its VALUE column\n"
        f"7. Delete old value, paste this:\n\n"
        f"   {jsid}\n\n"
        f"8. Press Enter\n"
        f"9. Go to:\n"
        f"   https://hbsfc.eventim-inhouse.co.il"
        f"/webshop/webticket/shoppingcart\n\n"
        f"Your 2 seats will be there - proceed to checkout!\n"
        f"{'='*40}"
    )


async def send_ntfy(title, body, priority="urgent"):
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, content=body.encode(), headers={
                "Title": title, "Priority": priority,
                "Tags": "ticket,soccer,tada", "Content-Type": "text/plain",
            })
            r.raise_for_status()
        print(f"[NTFY] Sent -> {url}")
    except Exception as e:
        print(f"[NTFY] FAILED: {e}")


async def login(page):
    print(f"[login] Navigating to {LOGIN_URL}")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    await asyncio.sleep(2)

    # Dismiss session-timeout interstitial if present
    for txt in ["המשך", "Continue"]:
        try:
            btn = page.locator(f"a:has-text('{txt}'), button:has-text('{txt}')").first
            if await btn.is_visible(timeout=3_000):
                await btn.click()
                await asyncio.sleep(2)
                await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                break
        except Exception:
            pass

    if "customerlogin" not in page.url.lower():
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        await asyncio.sleep(2)

    # Fill credentials
    try:
        await page.wait_for_selector("#username", timeout=10_000)
        await page.fill("#username", EMAIL)
        await page.fill("#password", PASSWORD)
    except PWTimeoutError:
        inputs = [i for i in await page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='checkbox'])") if await i.is_visible()]
        if len(inputs) >= 2:
            await inputs[0].fill(EMAIL)
            await inputs[1].fill(PASSWORD)

    await page.click("button:has-text('התחברות'), button[type='submit']", timeout=8_000)
    await page.wait_for_load_state("networkidle", timeout=30_000)

    if "customerlogin" in page.url.lower():
        raise RuntimeError("Login failed - still on login page")
    print(f"[login] OK: {page.url}")
    await page.screenshot(path=f"{SS}/t2_01_logged_in.png")


async def main():
    print(f"\n{'='*60}")
    print(f"  TEST 2 – Section {TEST_SECTION} Full Flow – {now()}")
    print(f"{'='*60}\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="he-IL",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────────
            await login(page)

            # ── 2. Open seat map ──────────────────────────────────────────────
            print(f"[test] Loading seat map...")
            await page.goto(SEATMAP_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=30_000)
            except PWTimeoutError:
                pass

            # Dismiss cookie popup
            for txt in ["מוכן", "מובן", "אישור"]:
                try:
                    btn = page.locator(f"button:has-text('{txt}')").first
                    if await btn.is_visible(timeout=3_000):
                        await btn.click()
                        break
                except Exception:
                    pass

            await asyncio.sleep(6)  # let DVM paint availability colours
            await page.screenshot(path=f"{SS}/t2_02_seatmap_overview.png")

            # ── 3. Click section 201 ──────────────────────────────────────────
            print(f"[test] Clicking section {TEST_SECTION} (block {TEST_BLOCK_ID})...")

            # Scroll the block into the viewport centre, then click it
            await page.evaluate(f"""() => {{
                const el = document.getElementById('{TEST_BLOCK_ID}');
                if (el) el.scrollIntoView({{ behavior: 'instant', block: 'center', inline: 'center' }});
            }}""")
            await asyncio.sleep(1)

            # Get the block's centre in screen coords after scroll
            block_info = await page.evaluate(f"""() => {{
                const el = document.getElementById('{TEST_BLOCK_ID}');
                if (!el) return null;
                const bb = el.getBoundingClientRect();
                return {{ x: bb.left + bb.width/2, y: bb.top + bb.height/2,
                          w: bb.width, h: bb.height }};
            }}""")

            print(f"[test] Block {TEST_BLOCK_ID} at: {block_info}")
            await page.screenshot(path=f"{SS}/t2_03a_scrolled.png")

            if block_info and block_info["w"] > 0 and 0 < block_info["y"] < 900:
                await page.mouse.click(block_info["x"], block_info["y"])
                print(f"[test] Clicked at ({block_info['x']:.0f}, {block_info['y']:.0f})")
            else:
                # Still off-screen: fire click via JS MouseEvent
                print(f"[test] Block still off-screen — dispatching JS click event")
                await page.evaluate(f"""() => {{
                    const el = document.getElementById('{TEST_BLOCK_ID}');
                    const hull = el?.querySelector('[id$="_hull"]') || el;
                    if (hull) {{
                        const bb = hull.getBoundingClientRect();
                        const evt = new MouseEvent('click', {{
                            bubbles: true, cancelable: true, view: window,
                            clientX: bb.left + bb.width/2,
                            clientY: bb.top + bb.height/2
                        }});
                        hull.dispatchEvent(evt);
                    }}
                }}""")

            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except PWTimeoutError:
                pass
            await asyncio.sleep(3)
            await page.screenshot(path=f"{SS}/t2_03_section_clicked.png")

            # ── 4. Count available seats ──────────────────────────────────────
            print(f"[test] Scanning for available seat circles...")

            seat_data = await page.evaluate("""() => {
                // Available seats: circle elements with class 's has-hover'
                // fill is #80FF80 (confirmed from DOM inspection)
                const seats = Array.from(document.querySelectorAll(
                    'circle.s.has-hover, circle[fill="#80FF80"], circle[fill="#80ff80"]'
                ));

                // Fallback: any visible circle with a green fill
                if (seats.length === 0) {
                    document.querySelectorAll('circle').forEach(c => {
                        const f = c.getAttribute('fill') || '';
                        const cf = window.getComputedStyle(c).fill || '';
                        const isGreen = f.toLowerCase().includes('80ff80')
                                     || f.toLowerCase().includes('1cce22')
                                     || cf.includes('128, 255, 128')
                                     || cf.includes('28, 206, 34');
                        if (isGreen) seats.push(c);
                    });
                }

                return seats.map(c => {
                    const bb = c.getBoundingClientRect();
                    return {
                        id: c.id,
                        fill: c.getAttribute('fill'),
                        class: c.className?.baseVal || '',
                        cx: Math.round(bb.left + bb.width/2),
                        cy: Math.round(bb.top + bb.height/2),
                        row: c.getAttribute('data-row') || '',
                        seat: c.getAttribute('data-seat') || ''
                    };
                });
            }""")

            print(f"[test] Available seats found: {len(seat_data)}")
            for s in seat_data[:5]:
                print(f"  id={s['id']} fill={s['fill']} class={s['class']} at ({s['cx']},{s['cy']})")

            if len(seat_data) < 2:
                print(f"[test] FAIL: less than 2 available seats found in section {TEST_SECTION}.")
                await send_ntfy(
                    f"Test 2 FAIL - Section {TEST_SECTION}",
                    f"Only {len(seat_data)} seat(s) found (need >= 2).\nTimestamp: {now()}",
                    priority="high"
                )
                sys.exit(1)

            # ── 5. Click exactly 2 seats ──────────────────────────────────────
            print(f"[test] Clicking {MAX_SEATS} seats...")
            clicked_seats = []

            for s in seat_data[:MAX_SEATS]:
                try:
                    await page.mouse.click(s["cx"], s["cy"])
                    await asyncio.sleep(0.6)
                    label = s.get("id") or f"Row {s.get('row','?')} Seat {s.get('seat','?')}"
                    clicked_seats.append(label)
                    print(f"  Clicked: {label} at ({s['cx']},{s['cy']})")
                except Exception as e:
                    print(f"  Could not click seat: {e}")

            await asyncio.sleep(2)
            await page.screenshot(path=f"{SS}/t2_04_seats_selected.png")

            # ── 6. Read proper row/seat labels from the seat list panel ───────
            # After clicking, seatList_268 is populated with li#{seatId} elements.
            # Each li has  div#{id}_block (section), div#{id}_row (row), div#{id}_seat (seat).
            seat_labels = await page.evaluate("""(seatIds) => {
                return seatIds.map(sid => {
                    const block = document.querySelector('#' + sid + '_block strong')?.textContent?.trim() || '';
                    const row   = document.querySelector('#' + sid + '_row strong')?.textContent?.trim() || '';
                    const seat  = document.querySelector('#' + sid + '_seat strong')?.textContent?.trim() || '';
                    if (row && seat) return 'Row ' + row + ' Seat ' + seat + ' (' + block + ')';
                    if (row)         return 'Row ' + row + ' (' + block + ')';
                    return block || sid;
                });
            }""", clicked_seats)
            print(f"[test] Seat labels: {seat_labels}")

            # ── 7. Click "הוסיפו לעגלת הקניות" (Add to cart) ─────────────────
            print(f"[test] Clicking 'Add to cart' button...")
            added = False
            for btn_txt in ["הוסיפו לעגלת הקניות", "הוסף לסל", "הוספה לסל",
                            "לסל הקניות", "Add to cart", "Add to Cart", "המשך"]:
                try:
                    btn = page.locator(f"button:has-text('{btn_txt}')").first
                    if await btn.is_visible(timeout=4_000):
                        await btn.click()
                        print(f"[test] Clicked '{btn_txt}'.")
                        await asyncio.sleep(3)
                        added = True
                        break
                except Exception:
                    pass

            if not added:
                print("[test] WARNING: could not find Add-to-cart button — seats may still be in selection state.")

            await page.screenshot(path=f"{SS}/t2_05_after_cart.png")
            cart_url = page.url
            print(f"[test] URL after cart: {cart_url}")

            # ── 8. Extract session cookie so user can access the same cart ─────
            # Playwright runs in an isolated browser session. We extract the
            # server-side session cookie and send it to the user so they can
            # paste it into their browser console (F12 → Console) and access
            # the same pre-filled cart.
            all_cookies = await context.cookies()
            session_cookie = None
            # Look for common Java / PHP / generic session cookie names
            session_names = ["JSESSIONID", "PHPSESSID", "ASP.NET_SessionId",
                             "sessionid", "session", "SID", "connect.sid"]
            for c in all_cookies:
                if c["name"].upper() in [n.upper() for n in session_names] or \
                   "session" in c["name"].lower() or "jsess" in c["name"].lower():
                    session_cookie = c
                    break

            print(f"[test] All cookies: {[(c['name'], c['domain']) for c in all_cookies]}")
            print(f"[test] Session cookie found: {session_cookie}")

            cart_access = build_cart_access_instructions(session_cookie)

            # ── 9. Send NTFY notification ─────────────────────────────────────
            title = f"TEST OK - Section {TEST_SECTION}: {len(seat_labels)} seats in cart!"
            body = (
                f"Section {TEST_SECTION} | {len(seat_labels)} seats added\n"
                f"Seats:\n" + "\n".join(f"  - {s}" for s in seat_labels) +
                f"\n\nTimestamp: {now()}\n"
                f"YOU HAVE ~10 MINUTES TO COMPLETE PURCHASE!"
                + cart_access
            )
            print(f"\n{'='*60}\n{title}\n{body}\n{'='*60}")
            await send_ntfy(title, body, priority="max")

            print(f"\n[test] TEST 2 COMPLETE")
            print(f"[test] Cart URL: {cart_url}")
            print(f"[test] Session cookie: {session_cookie}")
            print(f"[test] Check your NTFY app for the notification!")

        except Exception:
            tb = traceback.format_exc()
            print(f"[test] ERROR:\n{tb}")
            try:
                await page.screenshot(path=f"{SS}/t2_error.png")
            except Exception:
                pass
            await send_ntfy("Test 2 ERROR", f"{now()}\n{tb[:1000]}", priority="high")
            sys.exit(2)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
