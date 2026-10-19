"""
HBS vs Juventus – Ticket Availability Checker (bestseatselectbyblock version)
=============================================================================
Target page (post-login):
  https://hbsfc.eventim-inhouse.co.il/webshop/webticket/bestseatselectbyblock?eventId=268&upsellNo=0

DOM structure (confirmed via live browser inspection 2026-10-17):

  The page shows each section (119-123, 201-204) as a row containing:
    - <h4> with the section number
    - <fieldset> with a quantity <input type="number">

  SOLD OUT section:
    input id=""  name=""  max="0"   → "כרטיסים באזור זה אזלו"

  AVAILABLE section:
    input id="amount-X-0"  name="amount_SECTION_2002_"  max=">0"

  There is ONE shared "הוסיפו לעגלת הקניות" button for all sections.

Flow per run:
  1. Navigate to TARGET_URL to prime the session (click המשך if needed).
  2. Log in.
  3. Navigate to TARGET_URL — wait for content to render.
  4. For each of sections 119-123: check if available (max > 0).
  5. For every available section: set its quantity input to max.
  6. If any section had tickets: click "הוסיפו לעגלת הקניות" once.
  7. Send NTFY push + email alerts.

Environment variables (GitHub Secrets):
  LOGIN_EMAIL       – Eventim account e-mail
  LOGIN_PASSWORD    – Eventim account password
  NTFY_TOPIC        – ntfy.sh topic            (default: hbs-shefa)
  NTFY_SERVER       – ntfy server base URL      (default: https://ntfy.sh)
  EMAIL_SENDER      – Gmail address that sends alerts (needs App Password)
  EMAIL_APP_PASSWORD– Gmail App Password
  EMAIL_RECIPIENTS  – comma-separated recipients
"""

import asyncio
import io
import os
import smtplib
import ssl
import sys
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

# ── UTF-8 output ───────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Configuration ──────────────────────────────────────────────────────────────
TARGET_SECTIONS = ["119", "120", "121", "122", "123"]

LOGIN_URL   = "https://hbsfc.eventim-inhouse.co.il/webshop/webticket/customerlogin.secure"
TARGET_URL  = ("https://hbsfc.eventim-inhouse.co.il/webshop/webticket/"
               "bestseatselectbyblock?eventId=268&upsellNo=0")

EMAIL    = os.environ.get("LOGIN_EMAIL",    "")
PASSWORD = os.environ.get("LOGIN_PASSWORD", "")

NTFY_TOPIC  = os.environ.get("NTFY_TOPIC",  "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

EMAIL_SENDER       = os.environ.get("EMAIL_SENDER",       "")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
EMAIL_RECIPIENTS   = [
    addr.strip()
    for addr in os.environ.get("EMAIL_RECIPIENTS", "").split(",")
    if addr.strip()
]

SS = "screenshots"
os.makedirs(SS, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def build_cart_instructions(session_cookie: dict | None) -> str:
    if not session_cookie:
        return f"\n\nDirect link:\n{TARGET_URL}"
    jsid = session_cookie["value"]
    return (
        f"\n\n{'='*40}\n"
        f"HOW TO ACCESS YOUR PRE-FILLED CART\n"
        f"{'='*40}\n"
        f"1. Open Chrome on the site (logged in)\n"
        f"2. Press F12 → Application tab\n"
        f"3. Storage > Cookies > hbsfc.eventim-inhouse.co.il\n"
        f"4. Find JSESSIONID → double-click Value → paste:\n\n"
        f"   {jsid}\n\n"
        f"5. Press Enter → go to:\n"
        f"   https://hbsfc.eventim-inhouse.co.il/webshop/webticket/shoppingcart\n\n"
        f"YOU HAVE ~10 MINUTES TO COMPLETE PURCHASE!\n"
        f"{'='*40}"
    )


async def send_ntfy(title: str, body: str, priority: str = "urgent") -> None:
    priority_map = {"max": 5, "urgent": 5, "high": 4, "default": 3, "low": 2, "min": 1}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                NTFY_SERVER,
                json={
                    "topic":    NTFY_TOPIC,
                    "title":    title,
                    "message":  body,
                    "priority": priority_map.get(priority, 5),
                    "tags":     ["ticket", "soccer", "tada"],
                },
            )
            resp.raise_for_status()
        print(f"[NTFY] Sent -> {NTFY_SERVER}/{NTFY_TOPIC}")
    except Exception as exc:
        print(f"[NTFY] FAILED: {exc}")


def send_email(subject: str, body: str) -> None:
    if not EMAIL_SENDER or not EMAIL_APP_PASSWORD:
        print("[Email] Skipped – EMAIL_SENDER or EMAIL_APP_PASSWORD not set.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"HBS Ticket Checker <{EMAIL_SENDER}>"
        msg["To"]      = ", ".join(EMAIL_RECIPIENTS)
        msg.attach(MIMEText(body, "plain", "utf-8"))
        html = (
            "<html><body><pre style='font-family:monospace;font-size:14px;'>"
            + body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            + "</pre></body></html>"
        )
        msg.attach(MIMEText(html, "html", "utf-8"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo(); s.starttls(context=ctx)
            s.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, msg.as_string())
        print(f"[Email] Sent to: {', '.join(EMAIL_RECIPIENTS)}")
    except Exception as exc:
        print(f"[Email] FAILED: {exc}")


# ── Login ──────────────────────────────────────────────────────────────────────
async def do_login(page) -> bool:
    """
    Session-priming login flow:
      1. Navigate to TARGET_URL first → click המשך interstitial (primes session).
      2. Navigate to LOGIN_URL → fill credentials → submit.
    Without step 1, TARGET_URL renders an empty shell after login.
    """
    print(f"[{now()}] Priming session via target URL...")
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)
    await asyncio.sleep(2)

    for txt in ["המשך", "Continue"]:
        try:
            btn = page.locator(f"a:has-text('{txt}'), button:has-text('{txt}')").first
            if await btn.is_visible(timeout=3_000):
                print(f"[login] Clicked interstitial: '{txt}'")
                await btn.click()
                await asyncio.sleep(2)
                break
        except Exception:
            pass

    if "customerlogin" not in page.url.lower():
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        await asyncio.sleep(2)

    await page.screenshot(path=f"{SS}/01_login.png")

    # Fill credentials
    filled = False
    for es, ps in [("#username", "#password"),
                   ("input[type='email']", "input[type='password']")]:
        try:
            await page.wait_for_selector(es, timeout=5_000)
            await page.fill(es, EMAIL)
            await page.fill(ps, PASSWORD)
            filled = True
            print(f"[login] Filled via {es!r}")
            break
        except PWTimeoutError:
            pass

    if not filled:
        inputs = [i for i in await page.query_selector_all(
            "input:not([type=hidden]):not([type=submit])") if await i.is_visible()]
        if len(inputs) >= 2:
            await inputs[0].fill(EMAIL)
            await inputs[1].fill(PASSWORD)
            filled = True
            print("[login] Filled via visible inputs fallback")

    if not filled:
        print("[login] FAIL: no input fields found.")
        return False

    try:
        await page.click(
            "button[type='submit'], button:has-text('התחברות'), "
            "button:has-text('Login')", timeout=8_000)
    except PWTimeoutError:
        await page.keyboard.press("Enter")

    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except PWTimeoutError:
        pass
    await asyncio.sleep(1)
    print(f"[login] URL after submit: {page.url}")

    if "customerlogin" in page.url.lower():
        print("[login] FAIL: still on login page.")
        return False

    print(f"[login] OK. URL={page.url}")
    return True


# ── Section availability check ─────────────────────────────────────────────────
async def check_sections(page) -> list[dict]:
    """
    Scans the page for sections 119-123.
    Returns a list of dicts for sections that have tickets available:
      { section, input_id, input_name, max_qty }
    """
    return await page.evaluate("""(targetSections) => {
        const results = [];

        // Each section is in a .row containing an h4 with the section number
        const rows = Array.from(document.querySelectorAll('.evt-price-calculator .row'));

        for (const row of rows) {
            const h4 = row.querySelector('h4');
            if (!h4) continue;
            const sec = h4.textContent.trim();
            if (!targetSections.includes(sec)) continue;

            const input = row.querySelector('input[type="number"]');
            if (!input) continue;

            const maxQty = parseInt(input.getAttribute('max') || '0', 10);
            const hasName = !!input.name;

            // Available = max > 0 AND has a proper name attribute
            if (maxQty > 0 && hasName) {
                results.push({
                    section:    sec,
                    input_id:   input.id,
                    input_name: input.name,
                    max_qty:    maxQty,
                });
            }
        }
        return results;
    }""", TARGET_SECTIONS)


# ── Set quantities and add to cart ─────────────────────────────────────────────
async def set_quantities_and_add(page, available_sections: list[dict]) -> bool:
    """
    For each available section: click + once then set input to max_qty.
    Then click the shared "הוסיפו לעגלת הקניות" button once for all.
    Returns True if the cart button was clicked successfully.
    """
    result = await page.evaluate("""(sections) => {
        const rows = Array.from(document.querySelectorAll('.evt-price-calculator .row'));
        const done = [];

        for (const sec of sections) {
            // Find the row for this section
            const row = rows.find(r => {
                const h4 = r.querySelector('h4');
                return h4 && h4.textContent.trim() === sec.section;
            });
            if (!row) { done.push({section: sec.section, ok: false, reason: 'row not found'}); continue; }

            const input   = row.querySelector('input[type="number"]');
            const plusBtn = row.querySelector('.btn-plus');
            if (!input || !plusBtn)  { done.push({section: sec.section, ok: false, reason: 'no input/plus'}); continue; }

            // Click + once (triggers the page's quantity logic)
            plusBtn.click();

            // Then set directly to max and fire events
            if (sec.max_qty > 1) {
                input.value = String(sec.max_qty);
                input.dispatchEvent(new Event('input',  {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }
            done.push({section: sec.section, ok: true, qty: sec.max_qty});
        }
        return done;
    }""", available_sections)

    for r in result:
        if r.get("ok"):
            print(f"[cart] Section {r['section']}: quantity set to {r['qty']}")
        else:
            print(f"[cart] Section {r['section']}: FAILED - {r.get('reason')}")

    await asyncio.sleep(1.5)
    await page.screenshot(path=f"{SS}/05_quantities_set.png")

    # Click the shared "הוסיפו לעגלת הקניות" button
    try:
        btn = page.locator("button:has-text('הוסיפו לעגלת הקניות')").first
        if await btn.is_visible(timeout=5_000):
            await btn.click()
            print("[cart] Clicked 'הוסיפו לעגלת הקניות'.")
            await asyncio.sleep(3)
            await page.screenshot(path=f"{SS}/06_after_cart.png")
            return True
        else:
            print("[cart] Add-to-cart button not visible.")
            return False
    except Exception as exc:
        print(f"[cart] Could not click add-to-cart: {exc}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    print(f"\n{'='*60}")
    print(f"  HBS Ticket Checker - {now()}")
    print(f"  Sections: {', '.join(TARGET_SECTIONS)}")
    print(f"  URL: {TARGET_URL}")
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
            # ── 1. Login ───────────────────────────────────────────────────────
            if not await do_login(page):
                msg = f"Login failed at {now()}."
                await send_ntfy("HBS Checker - Login Failed", msg, priority="high")
                send_email("HBS Checker - Login Failed", msg)
                sys.exit(1)

            # ── 2. Load target page ────────────────────────────────────────────
            print(f"\n[{now()}] Loading target page...")
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=20_000)
            except PWTimeoutError:
                pass

            # Wait for section headings to render
            print("[main] Waiting for sections to render...")
            try:
                await page.wait_for_selector(
                    "h4, .evt-price-calculator",
                    timeout=20_000,
                )
            except PWTimeoutError:
                print("[main] WARNING: content timeout — continuing anyway.")
            await asyncio.sleep(2)
            await page.screenshot(path=f"{SS}/04_target_page.png")
            print(f"[main] Page title: {await page.title()}")

            # ── 3. Check sections 119-123 ──────────────────────────────────────
            available = await check_sections(page)

            print(f"\n[main] Sections checked: {', '.join(TARGET_SECTIONS)}")
            if available:
                for s in available:
                    print(f"  ✓ Section {s['section']}: AVAILABLE  max={s['max_qty']}")
            else:
                print("  All sections sold out — done.")
                sys.exit(0)

            # ── 4. Set quantities + add to cart ────────────────────────────────
            added = await set_quantities_and_add(page, available)

            # ── 5. Notify ──────────────────────────────────────────────────────
            all_cookies = await context.cookies()
            session_cookie = next(
                (c for c in all_cookies
                 if c["name"].upper() in ["JSESSIONID", "PHPSESSID"]
                 or "session" in c["name"].lower()
                 or c["name"] == "phoeniX"),
                None,
            )
            cart_info = build_cart_instructions(session_cookie)

            total_tickets = sum(s["max_qty"] for s in available)
            sections_str  = ", ".join(f"Section {s['section']} ({s['max_qty']} tickets)"
                                      for s in available)
            status = "ADDED TO CART" if added else "DETECTED (cart button failed)"

            title = (f"TICKET FOUND - {len(available)} section(s) available! "
                     f"({total_tickets} tickets total)")
            body = (
                f"Status: {status}\n\n"
                f"Available sections:\n"
                + "\n".join(f"  • Section {s['section']}: {s['max_qty']} ticket(s)"
                            for s in available)
                + f"\n\nTotal tickets in cart: {total_tickets}\n"
                f"Found at: {now()}\n"
                f"YOU HAVE ~10 MINUTES TO COMPLETE PURCHASE!"
                + cart_info
            )

            print(f"\n{'='*60}\n{title}\n{body}\n{'='*60}")
            await send_ntfy(title, body, priority="max")
            send_email(title, body)

        except Exception:
            tb = traceback.format_exc()
            print(f"[main] UNHANDLED ERROR:\n{tb}")
            try:
                await page.screenshot(path=f"{SS}/error.png")
            except Exception:
                pass
            err_subject = "HBS Checker - Unexpected Error"
            err_body    = f"{now()}\n\n{tb[:1500]}"
            await send_ntfy(err_subject, err_body, priority="high")
            send_email(err_subject, err_body)
            sys.exit(2)
        finally:
            await browser.close()

    print(f"\n=== Run complete at {now()} ===\n")


if __name__ == "__main__":
    asyncio.run(main())
