import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# Correctif Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Control Panel", layout="wide")

# --- STYLE SCHNEIDER ORIGINAL ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; border-radius: 5px; }
    .log-box { background: #2b2d2f; color: #00ff41; padding: 10px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 11px; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, success=True):
    t = datetime.now().strftime("%H:%M:%S")
    icon = "✅" if success else "❌"
    st.session_state.logs.insert(0, f"[{t}] {icon} {msg}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
    # On s'assure que le .gitignore ne bloque PAS le config.json
    with open(".gitignore", "w") as g:
        g.write("browser_session/\nnode_modules/\n")

# --- LOGIQUE CAPTURE & GIT ---
def run_capture(selected_channels):
    config = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Initialisation du navigateur Schneider...")
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Analyse du canal : {ch.upper()}")
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                try:
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{site.get('zoom', 100)/100}'")
                    time.sleep(site.get('wait_time', 5))
                    path = f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png"
                    page.screenshot(path=path, full_page=True)
                    add_log(f"Capture réussie pour {ch}_{i}")
                except Exception as e:
                    add_log(f"Erreur capture {ch}: {str(e)}", False)
        browser.close()

    try:
        repo = Repo("./")
        repo.git.add(all=True)
        # On force l'ajout de config.json au cas où
        repo.git.add('config.json', force=True)
        repo.index.commit(f"Sync {datetime.now().strftime('%H:%M')}")
        repo.remote(name='origin').push()
        add_log("Cloud mis à jour avec succès !", True)
    except Exception as e:
        add_log(f"Erreur Synchronisation : {str(e)}", False)

# --- INTERFACE ---
st.title("Schneider Electric | FactoryCast")
cfg = load_config()

col1, col2 = st.columns([2, 1])

with col1:
    st.header("⚙️ Configuration des Canaux")
    
    with st.expander("➕ Créer un nouveau canal", expanded=not cfg["channels"]):
        new_ch = st.text_input("Nom du canal (ex: Bureau, Atelier)")
        if st.button("Confirmer la création"):
            if new_ch:
                cfg["channels"][new_ch.lower()] = {"sites": []}
                save_config(cfg)
                st.rerun()

    for name, data in cfg["channels"].items():
        st.subheader(f"📍 Canal : {name.upper()}")
        for idx, s in enumerate(data["sites"]):
            with st.container():
                c_img, c_url, c_btn = st.columns([1, 3, 1])
                # Miniature
                img_path = f"{SCREENSHOT_DIR}{name.lower()}_{idx}.png"
                if os.path.exists(img_path):
                    c_img.image(img_path, width=150)
                else:
                    c_img.info("No img")
                
                s['active'] = c_url.toggle("Activer la diffusion", s.get('active', True), key=f"t{name}{idx}")
                s['url'] = c_url.text_input("Lien cible", s['url'], key=f"u{name}{idx}")
                
                z, w, d = c_url.columns(3)
                s['zoom'] = z.number_input("Zoom %", 10, 200, s.get('zoom', 100), key=f"z{name}{idx}")
                s['wait_time'] = w.number_input("Attente chargement (s)", 1, 60, s.get('wait_time', 10), key=f"w{name}{idx}")
                s['display_time'] = d.number_input("Temps affichage (s)", 5, 600, s.get('display_time', 30), key=f"d{name}{idx}")
                
                if c_btn.button("🗑️ Supprimer", key=f"del{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()
                if c_btn.button("🔑 Login Manuel", key=f"log{name}{idx}"):
                    subprocess.Popen(["python", "-c", f"from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); page = b.new_page(); page.goto('{s['url']}')"])
                st.divider()

        if st.button(f"➕ Ajouter un site à {name.upper()}", key=f"add{name}"):
            data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
            save_config(cfg); st.rerun()

with col2:
    st.header("🚀 Pilotage Live")
    sel = st.multiselect("Canaux à mettre à jour", list(cfg["channels"].keys()), default=list(cfg["channels"].keys())[:1])
    if st.button("▶️ DÉMARRER LA CAPTURE GÉNÉRALE", type="primary"):
        run_capture(sel)
        st.rerun()
    
    st.header("📟 Console de Monitoring")
    st.markdown(f"<div class='log-box'>{'<br>'.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    
    st.header("🔗 Liens Directs (Diffusion)")
    for ch in cfg["channels"]:
        url = f"https://nicolasvoiron.github.io/root/index.html?canal={ch}"
        st.markdown(f"**{ch.upper()}** : [Lien Public]({url})")