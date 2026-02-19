import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# --- FIX WINDOWS (Playwright + Python 3.12) ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro v6", layout="wide")

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# CSS Custom
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    .console-box { background: #1a1a1a; color: #00ff00; padding: 15px; height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px; border-radius: 8px; }
    .stExpander { background: white !important; border-radius: 10px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False

def add_log(msg, type="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    color = {"WAIT": "#FFA500", "SUCCESS": "#00FF00", "ERROR": "#FF4B4B"}.get(type, "#00BCFF")
    st.session_state.logs.insert(0, f"<div><span style='color:#888'>[{t}]</span> <span style='color:{color}'>{msg}</span></div>")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config, sync_git=False):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
    if sync_git:
        try:
            repo = Repo("./")
            repo.git.add(all=True)
            repo.index.commit(f"Auto-Sync: {datetime.now().strftime('%H:%M:%S')}")
            repo.remote(name='origin').push()
            add_log("Push GitHub SSH réussi", "SUCCESS")
        except Exception as e: add_log(f"Erreur Git: {e}", "ERROR")

# --- MOTEUR DE CAPTURE ---
def run_capture(ch_id, idx, s):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            add_log(f"Capture {ch_id}_{idx} en cours...")
            page.goto(s['url'], wait_until="networkidle", timeout=60000)
            page.evaluate(f"document.body.style.zoom = '{s['zoom']}%'")
            
            # Scroll forçage
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, 0)")
            
            # Attente (Wait Time)
            for r in range(s['wait_time'], 0, -1):
                if r % 10 == 0 or r <= 5: add_log(f"Stabilisation {ch_id}_{idx}: {r}s", "WAIT")
                time.sleep(1)
            
            raw = f"{SCREENSHOT_DIR}raw.png"
            page.screenshot(path=raw, full_page=True)
            
            # Traitement image
            img = Image.open(raw)
            w, h = img.size
            n = s.get('split', 1)
            sh = h // n
            for i in range(n):
                img.crop((0, i*sh, w, (i+1)*sh if i<n-1 else h)).save(f"{SCREENSHOT_DIR}{ch_id}_{idx}_p{i}.png")
            
            browser.close()
            return True
        except Exception as e:
            add_log(f"Erreur capture: {e}", "ERROR")
            return False

# --- INTERFACE ---
cfg = load_config()
st.title("Schneider Electric | FactoryCast v6")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("⚙️ Paramétrage")
    
    # On travaille sur une copie pour le renommage
    new_channels = {}
    
    for old_name, data in cfg["channels"].items():
        with st.expander(f"📍 POINT : {old_name.upper()}", expanded=True):
            # 1. RENOMMAGE
            c_name = st.text_input("Nom du point", old_name, key=f"rename_{old_name}")
            new_channels[c_name] = data
            
            for i, s in enumerate(data["sites"]):
                st.markdown(f"**Site #{i}**")
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
                s['url'] = c1.text_input("URL", s['url'], key=f"u{old_name}{i}")
                s['zoom'] = c2.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{old_name}{i}")
                s['wait_time'] = c3.number_input("Wait (s)", 0, 300, s['wait_time'], key=f"w{old_name}{i}")
                s['display_time'] = c4.number_input("Show (s)", 5, 600, s['display_time'], key=f"d{old_name}{i}")
                s['refresh_freq'] = c5.number_input("MàJ (sec)", 10, 86400, s.get('refresh_freq', 300), key=f"r{old_name}{i}")
                
                sc1, sc2, sc3 = st.columns([1, 2, 2])
                s['split'] = sc1.selectbox("Split", [1, 2, 3], index=s['split']-1, key=f"s{old_name}{i}")
                
                # LOGIN MANUEL CORRIGÉ
                if sc2.button(f"🔑 Login Manuel #{i}", key=f"log{old_name}{i}"):
                    # On utilise un script multi-ligne propre pour éviter le SyntaxError
                    script = (
                        "import sys, asyncio; "
                        "from playwright.sync_api import sync_playwright; "
                        "if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy()); "
                        "with sync_playwright() as p: "
                        "    b = p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); "
                        "    pg = b.new_page(); "
                        "    pg.goto('" + s['url'] + "'); "
                        "    pg.wait_for_event('close', timeout=0)"
                    )
                    subprocess.Popen([sys.executable, "-c", script])

                if sc3.button(f"🗑️ Retirer", key=f"del{old_name}{i}"):
                    data["sites"].pop(i); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter site à {old_name}", key=f"add{old_name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1, "refresh_freq": 300})
                save_config(cfg); st.rerun()
            
            if st.button(f"❌ Supprimer {old_name}", key=f"rmp{old_name}"):
                del new_channels[c_name]; cfg["channels"] = new_channels; save_config(cfg); st.rerun()

    cfg["channels"] = new_channels

    if st.button("➕ CRÉER UN NOUVEAU POINT"):
        cfg["channels"][f"point_{len(cfg['channels'])+1}"] = {"sites": []}
        save_config(cfg); st.rerun()

    if st.button("💾 SAUVEGARDER & SYNCHRONISER", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True); st.success("Config synchronisée !")

with col_right:
    st.subheader("🚀 Pilotage")
    active = st.multiselect("Canaux actifs", list(cfg["channels"].keys()), default=list(cfg["channels"].keys()))
    
    if not st.session_state.is_running:
        if st.button("▶️ DÉMARRER L'AUTOMATE", type="primary", use_container_width=True):
            st.session_state.is_running = True; st.rerun()
    else:
        if st.button("🛑 ARRÊTER", type="secondary", use_container_width=True):
            st.session_state.is_running = False; st.rerun()
    
    st.markdown("### 📝 Monitoring")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)

# --- BOUCLE AUTO ---
if st.session_state.is_running:
    changed = False
    for ch in active:
        for idx, site in enumerate(cfg["channels"][ch]["sites"]):
            last = site.get('last_ts', 0)
            if (time.time() - last) > site['refresh_freq']:
                if run_capture(ch, idx, site):
                    site['last_ts'] = time.time()
                    site['last_update_str'] = datetime.now().strftime("%H:%M:%S")
                    changed = True
    if changed: save_config(cfg, sync_git=True)
    time.sleep(5)
    st.rerun()