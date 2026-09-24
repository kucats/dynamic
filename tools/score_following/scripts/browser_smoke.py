"""Real browser audio paths. Always retain failures as well as successful screenshots."""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    output = Path("evidence/browser")
    output.mkdir(parents=True, exist_ok=True)
    results, errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"]
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 1080})
        page.on("pageerror", lambda e: errors.append(str(e)))
        for transport in ("pcm", "webrtc"):
            record = dict(transport=transport, passed=False, checks=[])
            try:
                await page.goto(os.getenv("SF_LAB_URL", "http://127.0.0.1:8765"))
                await page.wait_for_selector(".note")
                await page.select_option("#transport", transport)
                await page.click("#synthetic")
                await page.wait_for_function(
                    "window.labState?.event==='n015' || !document.querySelector('#error').hidden",
                    timeout=25000,
                )
                assert await page.locator("#error").is_hidden(), await page.locator("#error").inner_text()
                record["last_position"] = await page.evaluate("window.labState")
                record["checks"].append("audio end-to-end")
                await page.screenshot(path=str(output / f"{transport}.png"), full_page=True)
                await page.click("#pause")
                await page.wait_for_function("window.labState?.status==='paused'", timeout=5000)
                record["checks"].append("pause")
                await page.click("#pause")
                record["checks"].append("resume")
                await page.select_option("#anchor", "n000")
                await page.click("#seek")
                await page.wait_for_timeout(250)
                assert await page.locator("#error").is_hidden()
                record["checks"].append("seek")
                await page.click("#stop")
                await page.wait_for_function("document.querySelector('#connection').textContent==='未接続'")
                record["checks"].append("disconnect")
                record["passed"] = True
            except Exception as exc:
                record["failure"] = str(exc)
                record["diagnostics"] = await page.evaluate("""() => ({
                    state: window.labState, error: document.querySelector('#error')?.textContent,
                    log: document.querySelector('#log')?.textContent,
                    status: document.querySelector('#status')?.textContent,
                    freshness: document.querySelector('#freshness')?.textContent,
                    pitch: document.querySelector('#pitch')?.textContent,
                    connection: document.querySelector('#connection')?.textContent
                })""")
                await page.screenshot(path=str(output / f"{transport}-failure.png"), full_page=True)
            results.append(record)
            print(json.dumps(record, ensure_ascii=False))
            # Dispose transports even after failed startup; TTL is the server backstop.
            await page.goto("about:blank")
        mobile = "NOT RUN"
        try:
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.goto(os.getenv("SF_LAB_URL", "http://127.0.0.1:8765"))
            await page.wait_for_selector(".note")
            assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            await page.screenshot(path=str(output / "mobile-layout.png"), full_page=True)
            mobile = "PASS (Chromium emulation only; not Safari/iPhone)"
        except Exception as exc:
            mobile = f"FAIL: {exc}"
        result = dict(browser=browser.version, results=results, javascript_errors=errors, mobile_layout=mobile)
        (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await browser.close()
    if errors or not all(r["passed"] for r in results) or not mobile.startswith("PASS"):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
