import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

app = FastAPI(title="TikTok Automation Dashboard")

# ---------- Global Exception Handler ----------
# This ensures every unhandled error returns JSON, never plain text.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)[:400]}"}
    )

# In-memory session store: username -> cookies (JSON string)
sessions = {}

class LoginRequest(BaseModel):
    username: str
    password: str

class ActionRequest(BaseModel):
    account: str
    target: str


# ---------- Browser Helpers ----------

async def _start_browser() -> tuple[Playwright, Browser]:
    """Starts a Playwright browser with memory-optimised flags for low-RAM environments."""
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",           # Critical for 512MB RAM
            "--no-zygote",                # Required with --single-process
            "--disable-setuid-sandbox",
            "--disable-accelerated-2d-canvas",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=IsolateOrigins,site-per-process",
            "--blink-settings=imagesEnabled=false",
        ],
    )
    return p, browser


async def _new_context(browser: Browser, cookies_json: str | None = None) -> BrowserContext:
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    if cookies_json:
        cookies = json.loads(cookies_json)
        await context.add_cookies(cookies)
    return context


def _extract_video_url(target: str) -> str:
    if "tiktok.com" in target:
        return target
    if target.strip().isdigit():
        raise ValueError("Please provide the full TikTok video URL, not just the ID.")
    raise ValueError(
        "Invalid TikTok video URL. Example: https://www.tiktok.com/@user/video/1234567890"
    )


# ---------- API Endpoints (All with internal error handling) ----------

@app.post("/api/login")
async def login(req: LoginRequest):
    p = None
    browser = None
    try:
        p, browser = await _start_browser()
        context = await _new_context(browser)
        page = await context.new_page()
        await page.goto(
            "https://www.tiktok.com/login/phone-or-email/email",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(3)
        await page.fill('input[name="username"]', req.username, timeout=10000)
        await page.fill('input[type="password"]', req.password, timeout=10000)
        await page.click('button[type="submit"]', timeout=10000)
        await asyncio.sleep(6)
        if "login" in page.url.lower():
            raise HTTPException(status_code=401, detail="Login failed. Check credentials.")
        cookies = await context.cookies()
        sessions[req.username] = json.dumps(cookies)
        return {"success": True, "message": f"Logged in as @{req.username}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login error: {type(e).__name__}: {str(e)[:300]}")
    finally:
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass


@app.post("/api/follow")
async def follow(req: ActionRequest):
    if req.account not in sessions:
        raise HTTPException(status_code=401, detail="Account not logged in.")
    p = None
    browser = None
    try:
        p, browser = await _start_browser()
        context = await _new_context(browser, sessions[req.account])
        page = await context.new_page()
        await page.goto(
            f"https://www.tiktok.com/@{req.target.lstrip('@')}",
            wait_until="domcontentloaded", timeout=30000,
        )
        await asyncio.sleep(4)
        follow_btn = await page.query_selector(
            '[data-e2e="browse-follow"], button:has-text("Follow")'
        )
        if follow_btn:
            await follow_btn.click()
            await asyncio.sleep(1.5)
            return {"success": True, "message": f"Followed @{req.target}"}
        return {"success": False, "message": "Follow button not found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Follow error: {type(e).__name__}: {str(e)[:300]}")
    finally:
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass


@app.post("/api/like")
async def like(req: ActionRequest):
    if req.account not in sessions:
        raise HTTPException(status_code=401, detail="Account not logged in.")
    try:
        video_url = _extract_video_url(req.target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    p = None
    browser = None
    try:
        p, browser = await _start_browser()
        context = await _new_context(browser, sessions[req.account])
        page = await context.new_page()
        await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        like_btn = await page.query_selector(
            '[data-e2e="like-icon"], [data-e2e="browse-like-icon"]'
        )
        if like_btn:
            await like_btn.click()
            await asyncio.sleep(1.5)
            return {"success": True, "message": f"Liked video: {video_url}"}
        return {"success": False, "message": "Like button not found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Like error: {type(e).__name__}: {str(e)[:300]}")
    finally:
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass


@app.post("/api/view")
async def view(req: ActionRequest):
    if req.account not in sessions:
        raise HTTPException(status_code=401, detail="Account not logged in.")
    try:
        video_url = _extract_video_url(req.target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    p = None
    browser = None
    try:
        p, browser = await _start_browser()
        context = await _new_context(browser, sessions[req.account])
        page = await context.new_page()
        await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)
        return {"success": True, "message": f"View simulated for {video_url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"View error: {type(e).__name__}: {str(e)[:300]}")
    finally:
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass


@app.get("/api/accounts")
async def accounts():
    return {"accounts": list(sessions.keys())}


# ---------- Embedded Frontend (Responsive) ----------
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TikTok Automation Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style> body { font-family: system-ui, -apple-system, sans-serif; } </style>
</head>
<body class="bg-gray-100 min-h-screen">
  <div class="max-w-2xl mx-auto p-4 sm:p-6">
    <h1 class="text-2xl sm:text-3xl font-bold text-center text-gray-800 mb-6">TikTok Automation Dashboard</h1>

    <div class="bg-white rounded-lg shadow-md p-4 sm:p-6 mb-6">
      <h2 class="text-lg font-semibold mb-4 text-gray-700">1. Connect Account</h2>
      <form id="loginForm" class="flex flex-col sm:flex-row gap-3">
        <input id="username" type="text" placeholder="TikTok Username" required
          class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <input id="password" type="password" placeholder="Password" required
          class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <button type="submit"
          class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-2 rounded-lg transition">
          Login
        </button>
      </form>
      <p id="loginMsg" class="mt-3 text-sm text-gray-600"></p>
    </div>

    <div class="bg-white rounded-lg shadow-md p-4 sm:p-6 mb-6">
      <h2 class="text-lg font-semibold mb-4 text-gray-700">2. Select Connected Account</h2>
      <select id="accountSelect"
        class="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">-- Select an account --</option>
      </select>
      <button onclick="loadAccounts()" class="mt-2 text-sm text-blue-600 hover:underline">Refresh list</button>
    </div>

    <div class="bg-white rounded-lg shadow-md p-4 sm:p-6">
      <h2 class="text-lg font-semibold mb-4 text-gray-700">3. Perform Action</h2>
      <input id="target" type="text" placeholder="Target username (follow) or Video URL (like/view)"
        class="w-full border border-gray-300 rounded-lg px-4 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button onclick="doAction('follow')"
          class="bg-green-600 hover:bg-green-700 text-white font-medium py-3 rounded-lg transition">
          Follow User
        </button>
        <button onclick="doAction('like')"
          class="bg-red-500 hover:bg-red-600 text-white font-medium py-3 rounded-lg transition">
          Like Video
        </button>
        <button onclick="doAction('view')"
          class="bg-purple-600 hover:bg-purple-700 text-white font-medium py-3 rounded-lg transition">
          View Video
        </button>
      </div>
      <p id="actionMsg" class="mt-4 text-sm text-gray-600"></p>
    </div>
  </div>

  <script>
    const API = '';

    async function safeFetch(url, options) {
      const res = await fetch(url, options);
      const text = await res.text();
      try {
        return { ok: res.ok, status: res.status, data: JSON.parse(text) };
      } catch {
        throw new Error(`Server returned HTTP ${res.status} (not JSON). This usually means the container crashed.`);
      }
    }

    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      const msg = document.getElementById('loginMsg');
      msg.textContent = 'Logging in... (this may take 20-30 seconds)';
      msg.className = 'mt-3 text-sm text-gray-600';
      try {
        const { ok, data } = await safeFetch(API + '/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username, password})
        });
        if (ok) {
          msg.textContent = data.message;
          msg.className = 'mt-3 text-sm text-green-600';
          loadAccounts();
        } else {
          msg.textContent = 'Error: ' + data.detail;
          msg.className = 'mt-3 text-sm text-red-600';
        }
      } catch (err) {
        msg.textContent = 'Error: ' + err.message;
        msg.className = 'mt-3 text-sm text-red-600';
      }
    });

    async function loadAccounts() {
      const sel = document.getElementById('accountSelect');
      try {
        const { ok, data } = await safeFetch(API + '/api/accounts');
        if (!ok) return;
        sel.innerHTML = '<option value="">-- Select an account --</option>';
        data.accounts.forEach(acc => {
          const opt = document.createElement('option');
          opt.value = acc;
          opt.textContent = acc;
          sel.appendChild(opt);
        });
      } catch (e) { console.error(e); }
    }

    async function doAction(action) {
      const account = document.getElementById('accountSelect').value;
      const target = document.getElementById('target').value;
      const msg = document.getElementById('actionMsg');
      if (!account) { msg.textContent = 'Please select an account first.'; msg.className = 'mt-4 text-sm text-red-600'; return; }
      if (!target) { msg.textContent = 'Please enter a target.'; msg.className = 'mt-4 text-sm text-red-600'; return; }
      msg.textContent = 'Processing...';
      msg.className = 'mt-4 text-sm text-gray-600';
      try {
        const { ok, data } = await safeFetch(API + '/api/' + action, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({account, target})
        });
        if (ok) {
          msg.textContent = data.message;
          msg.className = 'mt-4 text-sm text-green-600';
        } else {
          msg.textContent = 'Error: ' + data.detail;
          msg.className = 'mt-4 text-sm text-red-600';
        }
      } catch (err) {
        msg.textContent = 'Error: ' + err.message;
        msg.className = 'mt-4 text-sm text-red-600';
      }
    }

    loadAccounts();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
