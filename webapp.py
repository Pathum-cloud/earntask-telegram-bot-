"""
Adsbitvex Web App integration reference.
Do NOT credit rewards based only on a client-side JavaScript promise.
Use this file as a guide when adding an actual ad page to FastAPI and implement
a provider-signed server-to-server callback before production rewards are enabled.
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/ad", response_class=HTMLResponse)
async def ad_page(uid: int):
    # The SDK in the provided screenshot is browser JavaScript, not a Telegram chat ad.
    # Verify Telegram WebApp initData server-side before trusting uid in production.
    return HTMLResponse(f"""
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Watch Ad & Earn</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#f5f7fb;margin:0;padding:24px;color:#172033}}
.card{{max-width:520px;margin:24px auto;background:white;border-radius:22px;padding:24px;box-shadow:0 8px 28px #13204012}}
h1{{font-size:24px}} .muted{{color:#65718a}} button{{background:#ef8b35;color:white;border:0;border-radius:12px;padding:14px 18px;font-weight:700;width:100%}}
</style></head><body><div class="card"><h1>📺 Watch Ads & Earn</h1>
<p class="muted">Reward: $0.05 per verified completed ad. Daily limit: 30.</p>
<p id="status">Load the ad below and watch it fully. Reward is credited only after provider-side verification.</p>
<div id="ad-slot"></div>
<script src="https://sdk.adsbitvex.com/functions/v1/ad-script?appid=000530"></script>
<script>
(async function(){{
  const status=document.getElementById('status');
  try {{
    if (typeof window.showadsbitvex !== 'function') {{
      status.textContent='Ad SDK did not load. Please retry later.'; return;
    }}
    await window.showadsbitvex();
    status.textContent='Ad session ended. Waiting for secure server-side verification; no balance has been credited yet.';
    // IMPORTANT: Never call a client endpoint to credit money just because this promise resolves.
    // Add provider-signed callback/API verification before issuing rewards.
  }} catch(e) {{ status.textContent='Ad could not be completed. Please retry later.'; }}
}})();
</script></div></body></html>""")
