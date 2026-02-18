import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="Schneider | FactoryCast Pro v4", layout="wide")

# --- STYLE SCHNEIDER ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .console-box { background: #121212; color: #00ff41; padding: 15px; height: 450px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; border: 1px solid #333; }
    .log-time { color: #888; } .log-step { color: #569cd6; } .log-wait { color: #ce9178; } .log-success { color: #3dcd58; font-weight: bold; }
    .stExpander { background: white !important; border-radius: 8px !important; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False

def add_log(msg, type="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    styles = {"STEP": "log-step", "WAIT": "log-wait", "SUCCESS": "log-success", "ERROR": "color:#f44747"}
    cls = styles.get(type, "")
    st.session_state.logs.insert(0, f"<div><span class='log-time'>[{t}]</span> <span class='{cls}'>{msg}</span></div>")

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
            repo.index.commit(f"Auto-update {datetime.now().strftime('%H:%M:%S')}")
            repo.remote(name='origin').push()
            add_log("Push GitHub terminé avec succès (SSH)", "SUCCESS")
        except Exception as e: add_log(f"Erreur Git : {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE ROBUSTE ---
def run_capture_sequence(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Démarrage du navigateur Schneider...", "STEP")
        # Fix Zoom : On définit une fenêtre immense pour le zoom
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_session", 
            headless=True,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1 # Base 1 pour éviter les flous
        )
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"--- CANAL : {ch.upper()} ---", "STEP")
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    add_log(f"Navigation : {s['url']}", "STEP")
                    page.goto(s['url'], timeout=90000, wait_until="load")
                    
                    # Application du Zoom via CSS Transform (plus fiable pour le rendu)
                    z_factor = s['zoom'] / 100
                    page.evaluate(f"document.body.style.zoom = '{z_factor}'")
                    
                    # COMPTE À REBOURS DANS LA CONSOLE
                    total_w = s['wait_time']
                    add_log(f"Attente de stabilisation ({total_w}s)...", "WAIT")
                    # On simule l'attente avec logs toutes les 5s
                    for remaining in range(total_w, 0, -5):
                        time.sleep(min(5, remaining))
                        add_log(f"  > Reste {max(0, remaining-5)}s...", "WAIT")

                    # CAPTURE
                    add_log(f"Prise de vue pour {ch}_{i}...", "STEP")
                    temp_p = f"{SCREENSHOT_DIR}raw.png"
                    page.screenshot(path=temp_p, full_page=True)
                    
                    # SPLIT LOGIC
                    img = Image.open(temp_p)
                    w, h = img.size
                    split_n = s.get('split', 1)
                    segment_h = h // split_n
                    for p_idx in range(split_n):
                        top = p_idx * segment_h
                        bottom = h if p_idx == split_n-1 else (p_idx+1) * segment_h
                        img.crop((0, top, w, bottom)).save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                    
                    s['last_update'] = datetime.now().strftime("%H:%M:%S")
                    add_log(f"Site {i} traité avec succès", "SUCCESS")
                except Exception as e: add_log(f"Erreur site {i}: {str(e)}", "ERROR")
        browser.close()
    save_config(cfg, sync_git=True)

# --- UI STREAMLIT ---
st.title("Schneider Electric | FactoryCast Pro")
cfg = load_config()

col_main, col_side = st.columns([2, 1])

with col_main:
    st.subheader("⚙️ Configuration")
    
    # Création point
    with st.expander("➕ Créer un nouveau point d'affichage"):
        t1, t2 = st.columns([3,1])
        n_ch = t1.text_input("Nom de l'écran", key="new_ch")
        if t2.button("Créer"):
            if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        with st.expander(f"📍 Point : {name.upper()}", expanded=True):
            st.write(f"🔗 [Lien Public](https://nicolasvoiron.github.io/root/index.html?canal={name})")
            
            for idx, s in enumerate(data["sites"]):
                st.markdown(f"**Écran #{idx}**")
                s1, s2 = st.columns([1, 4])
                img_p = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(img_p): s1.image(img_p)
                
                s['url'] = s2.text_input("URL", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4 = s2.columns(4)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Wait (s)", 1, 180, s['wait_time'], key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Show (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s['split']-1, key=f"s{name}{idx}")
                
                if s2.button(f"🔑 Login Manuel {name}_{idx}"):
                    subprocess.Popen(["python", "-c", f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"])
                if s2.button(f"🗑️ Retirer", key=f"rm{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter site à {name}", key=f"add{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            if st.button(f"❌ Supprimer {name}", key=f"del{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

    st.divider()
    if st.button("💾 SAUVEGARDER & SYNCHRONISER", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True)
        st.success("Config synchronisée !")

with col_side:
    st.subheader("🚀 Auto-Pilot")
    freq = st.slider("Fréquence capture (min)", 1, 60, 5)
    sel = st.multiselect("Ecrans à capturer", list(cfg["channels"].keys()))
    
    if not st.session_state.is_running:
        if st.button("▶️ DÉMARRER", type="primary", use_container_width=True):
            st.session_state.is_running = True; st.rerun()
    else:
        if st.button("🛑 ARRÊTER", type="primary", use_container_width=True):
            st.session_state.is_running = False; st.rerun()
        st.warning("🔄 Automate en cours...")

    st.markdown("### 📋 Console Détaillée")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)

if st.session_state.is_running:
    run_capture_sequence(sel)
    add_log(f"Repos {freq} min avant prochain cycle.", "WAIT")
    time.sleep(freq * 60)
    st.rerun()