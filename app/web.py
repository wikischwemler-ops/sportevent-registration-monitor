from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
HTML = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SportEvent Monitor</title>
<style>body{font-family:system-ui;margin:0;background:#f5f7fa;color:#172033}header{background:#172033;color:white;padding:24px}main{max-width:1200px;margin:24px auto;padding:0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card{background:white;border-radius:14px;padding:18px;box-shadow:0 2px 12px #0001}.badge{padding:5px 9px;border-radius:99px;background:#eef2f7;font-size:12px}a{color:#2457d6}</style></head>
<body><header><h1>SportEvent Registration Monitor</h1><div>Automatische Überwachung deiner Sportevent-Anmeldungen</div></header><main><h2>Meine Events</h2><div id="events" class="grid">Lade…</div></main>
<script>
async function load(){const r=await fetch('/api/dashboard'),d=await r.json(),root=document.getElementById('events');root.innerHTML='';
for(const e of d.events){const x=document.createElement('div');x.className='card';x.innerHTML='<h3>'+esc(e.name)+'</h3><span class="badge">'+esc(e.status)+'</span><p><b>Priorität:</b> '+esc(e.priority)+'</p><p><b>Event:</b> '+(e.event_date||'—')+'</p><p><b>Anmeldung:</b> '+(e.registration_start||'noch nicht bekannt')+'</p><p><b>Prüfintervall:</b> '+e.next_check_interval_minutes+' Min.</p>'+(e.registration_url?'<p><a target="_blank" href="'+e.registration_url+'">Zur Anmeldung</a></p>':'');root.appendChild(x)}}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))} load();setInterval(load,30000);
</script></body></html>'''
@router.get("/", response_class=HTMLResponse)
def home(): return HTML
