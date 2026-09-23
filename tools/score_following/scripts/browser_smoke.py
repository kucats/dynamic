"""Run against an explicitly started localhost lab, with original synthetic audio only."""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    output = Path("evidence/browser")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"]
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for transport in ("pcm", "webrtc"):
            await page.goto(os.getenv("SF_LAB_URL", "http://127.0.0.1:8765"))
            await page.wait_for_selector(".note")
            await page.select_option("#transport", transport)
            await page.click("#synthetic")
            await page.wait_for_function("window.labState?.event==='n015'", timeout=25000)
            assert await page.locator("#error").is_hidden(), await page.locator("#error").inner_text()
            state = await page.evaluate("window.labState")
            await page.screenshot(path=str(output / f"{transport}.png"), full_page=True)
            # Real UI pause/resume + re-anchor while stream is still connected.
            await page.click("#pause")
            await page.wait_for_function("window.labState?.status==='paused'", timeout=5000)
            await page.click("#pause")
            await page.select_option("#anchor", "n000")
            await page.click("#seek")
            await page.wait_for_timeout(250)
            assert await page.locator("#error").is_hidden()
            await page.click("#stop")
            await page.wait_for_function("document.querySelector('#connection').textContent==='未接続'")
            results.append(
                dict(
                    transport=transport,
                    passed=True,
                    last_position=state,
                    checks=["audio end-to-end", "pause", "resume", "seek", "disconnect"],
                )
            )
        # Mobile layout renders without horizontal page overflow. This is not Safari/iPhone audio validation.
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto(os.getenv("SF_LAB_URL", "http://127.0.0.1:8765"))
        await page.wait_for_selector(".note")
        assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        await page.screenshot(path=str(output / "mobile-layout.png"), full_page=True)
        assert not errors, errors
        result = dict(
            browser=browser.version,
            results=results,
            javascript_errors=errors,
            mobile_layout="PASS (Chromium emulation only; not Safari/iPhone)",
        )
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
