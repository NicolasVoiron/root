import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# --- CORRECTIF INDISPENSABLE POUR WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- CONFIGURATION VISUELLE SCHNEIDER ELECTRIC ---
st.set_page_config(page_title="FactoryCast Elite | Schneider Electric", layout="wide")

st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: var(--se-dark) !important; border-bottom: 2px solid var(--se-green); padding-bottom: 5px; }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; border: none; font-weight: bold; width: 100%; }
    .site-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 5px; border-left: 8px solid var(--se-green); background: #f9f9f9; }
    .log-box { background: #2b2d2f; color: #00ff41; font-family: monospace; padding: 10px; height: 300px; overflow-y: auto; font-size: 12px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, type="info"):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"[{t}] {'✅' if type=='success' else '❌' if type=='error' else '⚙️'} {msg}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                content = json.load(f)
                if "channels" in content: return content
        except: pass
    return {"channels": {"bureau": {"sites": []}}} # Valeur par défaut si vide

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# --- MOTEUR DE CAPTURE ---
def run_capture_cycle(selected_channels):
    config = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Démarrage du navigateur...")
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Traitement du canal : {ch}")
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                try:
                    add_log(f"Capture de {site['url']}")
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{site.get('zoom', 100)/100}'")
                    time.sleep(site.get('wait_time', 5))
                    page.screenshot(path=f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png", full_page=True)
                    add_log(f"Réussite : {ch}_{i}", "success")
                except Exception as e:
                    add_log(f"Erreur sur {ch}: {str(e)}", "error")
        browser.close()

    try:
        add_log("Envoi vers GitHub (SSH)...")
        repo = Repo("./")
        repo.git.add(all=True)
        repo.index.commit(f"Auto-update {datetime.now().strftime('%H:%M')}")
        repo.remote(name='origin').push()
        add_log("Cloud mis à jour !", "success")
    except Exception as e:
        add_log(f"Erreur Git : {str(e)}", "error")

# --- UI PRINCIPALE ---
st.title("Schneider Electric | FactoryCast")
cfg = load_config()

col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.header("⚙️ Configuration des Écrans")
    
    # Bouton pour créer un canal si la liste est vide
    if not cfg["channels"]:
        new_ch = st.text_input("Nom du premier point d'affichage (ex: Bureau)")
        if st.button("Initialiser"):
            cfg["channels"][new_ch.lower()] = {"sites": []}
            save_config(cfg)
            st.rerun()

    for name, data in cfg["channels"].items():
        with st.expander(f"📍 Point : {name.upper()}", expanded=True):
            for idx, s in enumerate(data["sites"]):
                st.markdown(f"<div class='site-card'>", unsafe_allow_html=True)
                s['active'] = st.toggle("Actif", s.get('active', True), key=f"t{name}{idx}")
                s['url'] = st.text_input("URL", s['url'], key=f"u{name}{idx}")
                c1, c2, c3 = st.columns(3)
                s['zoom'] = c1.number_input("Zoom %", 10, 200, s.get('zoom', 100), key=f"z{name}{idx}")
                s['wait_time'] = c2.number_input("Attente (s)", 1, 60, s.get('wait_time', 10), key=f"w{name}{idx}")
                s['display_time'] = c3.number_input("Affichage (s)", 5, 600, s.get('display_time', 30), key=f"d{name}{idx}")
                
                if st.button(f"🗑️ Supprimer", key=f"del{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if st.button(f"➕ Ajouter un site à {name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
                save_config(cfg); st.rerun()
    
    if st.button("💾 SAUVEGARDER LA CONFIGURATION"):
        save_config(cfg)
        st.success("Configuration enregistrée localement !")

with col_right:
    st.header("🚀 Pilotage Direct")
    sel = st.multiselect("Canaux à mettre à jour", list(cfg["channels"].keys()))
    if st.button("▶️ DÉMARRER LA CAPTURE", type="primary"):
        if sel:
            run_capture_cycle(sel)
            st.rerun()
    
    st.header("📟 Console Monitoring")
    st.markdown(f"<div class='log-box'>{'<br>'.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    
    st.header("🔗 Liens")
    for ch in cfg["channels"]:
        url = f"https://nicolasvoiron.github.io/root/index.html?canal={ch}"
        st.markdown(f"**{ch.upper()}** : [Ouvrir l'écran]({url})")