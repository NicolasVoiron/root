import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Control Panel", layout="wide")

st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; border-radius: 5px; }
    .log-box { background: #2b2d2f; color: #00ff41; padding: 10px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 11px; }
    .site-card { border: 1px solid #eee; padding: 15px; border-radius: 10px; margin-bottom: 10px; background: #fdfdfd; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, success=True):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"[{t}] {'✅' if success else '❌'} {msg}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)

def run_capture(selected_channels):
    config = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Lancement du navigateur...")
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        for ch in selected_channels:
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                try:
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{site.get('zoom', 100)/100}'")
                    time.sleep(site.get('wait_time', 5))
                    page.screenshot(path=f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png", full_page=True)
                    add_log(f"Capture OK : {ch}_{i}")
                except Exception as e: add_log(f"Erreur {ch}: {str(e)}", False)
        browser.close()

    try:
        repo = Repo("./")
        repo.git.add(all=True)
        repo.git.add('config.json', force=True) # Forçage intégré
        repo.index.commit(f"Auto-Sync {datetime.now().strftime('%H:%M')}")
        repo.remote(name='origin').push()
        add_log("GitHub mis à jour via SSH", True)
    except Exception as e: add_log(f"Erreur Git : {str(e)}", False)

# UI
st.title("Schneider Electric | FactoryCast")
cfg = load_config()

col1, col2 = st.columns([2, 1])

with col1:
    st.header("⚙️ Configuration")
    with st.expander("➕ Créer un nouveau canal", expanded=not cfg["channels"]):
        new_ch = st.text_input("Nom du canal")
        if st.button("Confirmer la création"):
            if new_ch:
                cfg["channels"][new_ch.lower()] = {"sites": []}
                save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        st.subheader(f"📍 Canal : {name.upper()}")
        for idx, s in enumerate(data["sites"]):
            st.markdown("<div class='site-card'>", unsafe_allow_html=True)
            c_img, c_ctrl = st.columns([1, 3])
            img_p = f"{SCREENSHOT_DIR}{name.lower()}_{idx}.png"
            if os.path.exists(img_p): c_img.image(img_p, width=150)
            
            s['url'] = c_ctrl.text_input("URL", s['url'], key=f"u{name}{idx}")
            z, w, d = c_ctrl.columns(3)
            s['zoom'] = z.number_input("Zoom %", 10, 200, s.get('zoom', 100), key=f"z{name}{idx}")
            s['wait_time'] = w.number_input("Attente (s)", 1, 60, s.get('wait_time', 10), key=f"w{name}{idx}")
            s['display_time'] = d.number_input("Affichage (s)", 5, 600, s.get('display_time', 30), key=f"d{name}{idx}")
            
            if c_ctrl.button(f"🔑 Login Manuel {name}_{idx}"):
                add_log(f"Ouverture navigateur pour {name}...")
                # Correction du login : le script attend que tu fermes la fenêtre
                cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); print('FERMEZ LE NAVIGATEUR POUR CONTINUER...'); pg.wait_for_event('close', timeout=0)"
                subprocess.Popen(["python", "-c", cmd])

            if c_ctrl.button(f"🗑️ Supprimer", key=f"del{name}{idx}"):
                data["sites"].pop(idx); save_config(cfg); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.button(f"➕ Ajouter site à {name.upper()}", key=f"add{name}"):
            data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
            save_config(cfg); st.rerun()

with col2:
    st.header("🚀 Pilotage")
    sel = st.multiselect("Canaux", list(cfg["channels"].keys()))
    if st.button("▶️ DÉMARRER LA CAPTURE", type="primary"):
        run_capture(sel); st.rerun()
    st.markdown(f"<div class='log-box'>{'<br>'.join(st.session_state.logs)}</div>", unsafe_allow_html=True)