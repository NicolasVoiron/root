import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# --- CORRECTIF WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Elite", layout="wide")

# Style Schneider
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; }
    .log-box { background: #2b2d2f; color: #00ff41; padding: 15px; height: 300px; overflow-y: auto; border-radius: 5px; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, type="info"):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"[{t}] {'✅' if type=='success' else '⚙️'} {msg}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)

def run_capture_cycle(selected_channels):
    config = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Démarrage du moteur de capture...")
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                try:
                    add_log(f"Capture en cours : {site['url']}")
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{site.get('zoom', 100)/100}'")
                    time.sleep(site.get('wait_time', 5))
                    page.screenshot(path=f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png", full_page=True)
                except Exception as e: add_log(f"Erreur : {str(e)}", "error")
        browser.close()

    # SYNC GITHUB (SSH)
    try:
        repo = Repo("./")
        repo.git.add(all=True)
        repo.index.commit(f"Sync {datetime.now().strftime('%H:%M')}")
        repo.remote(name='origin').push()
        add_log("Cloud mis à jour avec succès !", "success")
    except Exception as e: add_log(f"Erreur Sync SSH : {str(e)}")

# UI
st.title("FactoryCast Control Panel")
cfg = load_config()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("⚙️ Configuration des Écrans")
    # Gestion des canaux (BUREAU, etc.)
    for name, data in cfg["channels"].items():
        with st.expander(f"Point : {name.upper()}", expanded=True):
            for idx, s in enumerate(data["sites"]):
                s['url'] = st.text_input(f"URL {idx}", s['url'], key=f"u{name}{idx}")
                if st.button(f"🔑 Login Manuel {name}_{idx}"):
                    subprocess.Popen(["python", "-c", f"from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); page = b.new_page(); page.goto('{s['url']}')"])

with col2:
    st.subheader("🚀 Pilotage")
    sel = st.multiselect("Canaux", list(cfg["channels"].keys()))
    if st.button("DÉMARRER LA CAPTURE", type="primary"):
        run_capture_cycle(sel)
        st.rerun()
    
    st.markdown(f"<div class='log-box'>{'<br>'.join(st.session_state.logs)}</div>", unsafe_allow_html=True)