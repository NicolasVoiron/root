import streamlit as st
import time
import json
import os
import subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright
from PIL import Image
import asyncio

# Fix pour Windows 3.12 et Playwright
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- CONFIGURATION & STYLE SCHNEIDER ---
st.set_page_config(page_title="FactoryCast Pro v6", layout="wide")
SC_GREEN = "#3dcd58"
SC_DARK = "#333333"

st.markdown(f"""
    <style>
    .main {{ background-color: #f4f4f4; }}
    .stButton>button {{ background-color: {SC_GREEN}; color: white; border-radius: 0px; border: none; }}
    .status-box {{ padding: 10px; border-left: 5px solid {SC_GREEN}; background: white; margin-bottom: 10px; }}
    header {{ background-color: {SC_DARK} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION ---
CONFIG_FILE = "config.json"
DATA_DIR = "displays"
os.makedirs(DATA_DIR, exist_ok=True)

if 'config' not in st.session_state:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: st.session_state.config = json.load(f)
    else:
        st.session_state.config = {}

def save_config():
    with open(CONFIG_FILE, 'w') as f: json.dump(st.session_state.config, f, indent=4)

def git_sync(message):
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push"], check=True)
        return True
    except Exception as e:
        st.error(f"Erreur SSH/Git : {e}")
        return False

# --- LOGIQUE DE CAPTURE ---
def capture_site(canal, site_idx):
    site = st.session_state.config[canal]['sites'][site_idx]
    
    with sync_playwright() as p:
        # Utilisation du contexte persistant pour les cookies
        browser_type = p.chromium
        context = browser_type.launch_persistent_context(
            f"user_data/{canal}", 
            headless=True,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=site.get('zoom', 100) / 100
        )
        page = context.new_page()
        
        try:
            page.goto(site['url'], wait_until="networkidle")
            time.sleep(site.get('wait_time', 5))
            
            # Scroll "Anti-JS dormant"
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
            
            path = f"{DATA_DIR}/{canal}_{site_idx}.png"
            page.screenshot(path=path, full_page=True)
            
            # Gestion du Split (Découpage)
            segments = site.get('split', 1)
            if segments > 1:
                img = Image.open(path)
                w, h = img.size
                for i in range(segments):
                    top = (h / segments) * i
                    bottom = (h / segments) * (i + 1)
                    part = img.crop((0, top, w, bottom))
                    part.save(f"{DATA_DIR}/{canal}_{site_idx}_p{i}.png")
            
            st.session_state.config[canal]['sites'][site_idx]['last_update'] = datetime.now().strftime("%H:%M:%S")
            save_config()
        finally:
            context.close()

# --- INTERFACE UTILISATEUR ---
st.title("🏗️ FactoryCast Pro v6")
st.subheader("Contrôleur de Diffusion Industrielle")

tabs = st.tabs(["🎛️ Canaux", "🚀 Automate", "🔐 Sessions"])

with tabs[0]: # Gestion des Canaux
    canal_list = list(st.session_state.config.keys())
    new_canal = st.text_input("Ajouter un Point d'Affichage (ex: ATELIER_1)")
    if st.button("Créer le canal") and new_canal:
        st.session_state.config[new_canal] = {"sites": []}
        save_config()
        st.rerun()

    for canal in canal_list:
        with st.expander(f"Canal : {canal}"):
            for idx, site in enumerate(st.session_state.config[canal]['sites']):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                site['url'] = col1.text_input(f"URL", site['url'], key=f"u{canal}{idx}")
                site['zoom'] = col2.number_input("Zoom %", 10, 200, site['zoom'], key=f"z{canal}{idx}")
                site['split'] = col3.selectbox("Split", [1, 2, 3], index=site['split']-1, key=f"s{canal}{idx}")
                if col4.button("🗑️", key=f"d{canal}{idx}"):
                    st.session_state.config[canal]['sites'].pop(idx)
                    save_config()
                    st.rerun()
            
            if st.button(f"➕ Ajouter un site à {canal}"):
                st.session_state.config[canal]['sites'].append({"url": "", "zoom": 100, "wait_time": 5, "freq": 300, "duration": 15, "split": 1})
                save_config()
                st.rerun()

with tabs[1]: # Automate
    col_run, col_log = st.columns([1, 2])
    if col_run.button("▶️ DÉMARRER L'AUTOMATION", use_container_width=True):
        col_log.info("Lancement du cycle de capture...")
        while True:
            for canal in st.session_state.config:
                for idx, site in enumerate(st.session_state.config[canal]['sites']):
                    col_log.write(f"📸 Capture de {canal} - Site {idx}...")
                    capture_site(canal, idx)
            
            col_log.success("Push vers GitHub via SSH...")
            git_sync(f"Auto-update {datetime.now().strftime('%H:%M')}")
            time.sleep(30) # Attente avant prochain cycle

with tabs[2]: # Sessions
    st.info("Utilisez ce mode pour vous connecter manuellement aux ERP/Dashboards.")
    target_canal = st.selectbox("Choisir un canal", canal_list)
    if st.button("Ouvrir Navigateur (Mode Login)"):
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(f"user_data/{target_canal}", headless=False)
            page = browser.new_page()
            st.warning("Fermez la fenêtre du navigateur une fois connecté pour sauvegarder les cookies.")
            while len(browser.pages) > 0: time.sleep(1)