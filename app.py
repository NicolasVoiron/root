import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro | Auto-Pilot", layout="wide")

# --- STYLE SE PRO ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: white; }
    .channel-card { background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #ddd; border-top: 5px solid var(--se-green); margin-bottom: 20px; }
    .console-box { background: #121212; color: #00ff41; padding: 15px; height: 350px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 11px; border-radius: 5px; }
    .log-git { color: #ce9178; } .log-error { color: #f44747; } .log-success { color: #3dcd58; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False

def add_log(msg, level="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    style = {"INFO": "", "SUCCESS": "log-success", "ERROR": "log-error", "GIT": "log-git"}.get(level, "")
    st.session_state.logs.insert(0, f"<div><span style='color:#888'>[{t}]</span> <span class='{style}'>{msg}</span></div>")

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
            repo.git.add(CONFIG_FILE, force=True)
            repo.index.commit(f"Auto-Update {datetime.now().strftime('%H:%M')}")
            repo.remote(name='origin').push()
            add_log("Cloud GitHub à jour (SSH)", "GIT")
        except Exception as e: add_log(f"Erreur Git: {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE ---
def run_capture_sequence(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"--- CANAL : {ch.upper()} ---")
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    add_log(f"Navigation : {s['url']}")
                    page.goto(s['url'], timeout=60000, wait_until="load")
                    
                    page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
                    
                    # RESPECT STRICT DU WAIT TIME
                    add_log(f"Attente forcée (Refresh) : {s['wait_time']}s...")
                    time.sleep(s['wait_time'])
                    
                    temp_p = f"{SCREENSHOT_DIR}raw_{ch}_{i}.png"
                    page.screenshot(path=temp_p, full_page=True)
                    
                    # Split Logic
                    split_n = s.get('split', 1)
                    img = Image.open(temp_p)
                    w, h = img.size
                    segment_h = h // split_n
                    for p_idx in range(split_n):
                        top = p_idx * segment_h
                        bottom = h if p_idx == split_n - 1 else (p_idx + 1) * segment_h
                        img.crop((0, top, w, bottom)).save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                    
                    os.remove(temp_p)
                    s['last_update'] = datetime.now().strftime("%H:%M:%S")
                    add_log(f"Capture {i} réussie", "SUCCESS")
                except Exception as e: add_log(f"Erreur site {i}: {str(e)}", "ERROR")
        browser.close()
    save_config(cfg, sync_git=True)

# --- UI ---
st.title("Schneider Electric | FactoryCast Pro")
cfg = load_config()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("⚙️ Configuration des Canaux")
    # Gestion création canal
    t1, t2 = st.columns([3,1])
    n_ch = t1.text_input("Nouveau Canal", placeholder="Nom...", label_visibility="collapsed")
    if t2.button("➕ CRÉER"):
        if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        with st.container():
            st.markdown(f"<div class='channel-card'>", unsafe_allow_html=True)
            h1, h2, h3 = st.columns([3, 1, 1])
            h1.markdown(f"### 📍 Point : {name.upper()}")
            h1.info(f"🔗 [Lien Public](https://nicolasvoiron.github.io/root/index.html?canal={name})")
            
            if h3.button("🗑️ Suppr.", key=f"del_{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

            for idx, s in enumerate(data["sites"]):
                st.divider()
                s1, s2 = st.columns([1, 4])
                img_p = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(img_p): s1.image(img_p)
                
                s['url'] = s2.text_input("URL", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4 = s2.columns(4)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Refresh (s)", 1, 60, s['wait_time'], key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Affichage (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s['split']-1, key=f"s{name}{idx}")
                
                if s2.button(f"🔑 Login Manuel {name}_{idx}"):
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])
                if s2.button(f"🗑️ Retirer", key=f"rm_{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter site à {name.upper()}", key=f"add_{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.subheader("🚀 Pilotage Automatique")
    
    # PARAMETRE DE FREQUENCE DE CAPTURE
    freq = st.slider("Fréquence de capture globale (minutes)", 1, 60, 5)
    sel = st.multiselect("Canaux à surveiller", list(cfg["channels"].keys()))
    
    if not st.session_state.is_running:
        if st.button("▶️ DÉMARRER L'AUTO-PILOT", type="primary", use_container_width=True):
            st.session_state.is_running = True
            st.rerun()
    else:
        if st.button("🛑 ARRÊTER L'AUTO-PILOT", type="primary", use_container_width=True):
            st.session_state.is_running = False
            st.rerun()
        
        st.warning("🔄 Auto-Pilot Actif. Ne fermez pas cette page.")
        # La boucle de rafraîchissement
        run_capture_sequence(sel)
        add_log(f"Prochaine capture dans {freq} min...")
        time.sleep(freq * 60)
        st.rerun()

    st.divider()
    st.markdown("📜 **LOGS DÉTAILLÉS**")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)