import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# --- CONFIGURATION WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro | Schneider Electric", layout="wide")

# --- DESIGN SYSTEM ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; --se-light: #f4f4f4; }
    .stApp { background-color: #ffffff; }
    .main-header { color: var(--se-dark); border-left: 10px solid var(--se-green); padding-left: 20px; margin-bottom: 30px; }
    .stButton>button { border-radius: 4px; font-weight: 600; }
    .btn-save { background-color: var(--se-green) !important; color: white !important; width: 100%; border: none; padding: 10px; }
    .channel-card { background: var(--se-light); padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 20px; }
    .console-box { background: #1e1e1e; color: #d4d4d4; padding: 15px; height: 350px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; border-top: 5px solid #444; }
    .log-time { color: #888; }
    .log-git { color: #569cd6; }
    .log-success { color: #4ec9b0; }
    .log-error { color: #f44747; }
    .link-box { background: #e8f5e9; padding: 10px; border-radius: 4px; border: 1px solid #c8e6c9; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, level="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "⚙️", "SUCCESS": "✅", "ERROR": "❌", "GIT": "☁️"}
    color_class = {"INFO": "", "SUCCESS": "log-success", "ERROR": "log-error", "GIT": "log-git"}
    log_html = f"<div class='{color_class[level]}'><span class='log-time'>[{t}]</span> {icons[level]} {msg}</div>"
    st.session_state.logs.insert(0, log_html)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f: return json.load(f)
        except: pass
    return {"channels": {}}

def save_config(config, sync_git=False):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    if sync_git:
        try:
            repo = Repo("./")
            repo.git.add(all=True)
            repo.git.add('config.json', force=True)
            repo.index.commit(f"Update Config: {datetime.now().strftime('%H:%M')}")
            repo.remote(name='origin').push()
            add_log("Configuration synchronisée sur GitHub", "GIT")
            return True
        except Exception as e:
            add_log(f"Erreur Sync Git : {str(e)}", "ERROR")
    return False

# --- UI PRINCIPALE ---
st.markdown("<h1 class='main-header'>FactoryCast Pro <small style='font-size:15px; color:#666;'>v2.1 - Dashboard Industriel</small></h1>", unsafe_allow_html=True)
cfg = load_config()

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📁 Gestion des Canaux d'Affichage")
    
    # Barre d'outils Canal
    t1, t2 = st.columns([3, 1])
    new_ch_name = t1.text_input("", placeholder="Nom du nouveau canal (ex: ATELIER_SUD)", label_visibility="collapsed")
    if t2.button("➕ Créer Canal", use_container_width=True):
        if new_ch_name:
            cfg["channels"][new_ch_name.lower()] = {"sites": []}
            save_config(cfg)
            add_log(f"Canal '{new_ch_name}' créé localement")
            st.rerun()

    st.divider()

    # Liste des canaux
    for ch_name, data in list(cfg["channels"].items()):
        with st.container():
            st.markdown(f"<div class='channel-card'>", unsafe_allow_html=True)
            
            # Header du canal
            h1, h2, h3 = st.columns([3, 1, 1])
            h1.markdown(f"### 📍 Point : {ch_name.upper()}")
            
            # Lien de diffusion rapide
            public_url = f"https://nicolasvoiron.github.io/root/index.html?canal={ch_name}"
            h1.markdown(f"<div class='link-box'>🔗 <a href='{public_url}' target='_blank'>Accéder au lien de diffusion</a></div>", unsafe_allow_html=True)

            if h3.button("🗑️ Supprimer Canal", key=f"del_ch_{ch_name}"):
                del cfg["channels"][ch_name]
                save_config(cfg)
                st.rerun()

            # Liste des sites dans le canal
            for idx, site in enumerate(data["sites"]):
                st.markdown("---")
                s1, s2 = st.columns([1, 4])
                
                # Miniature
                img_path = f"{SCREENSHOT_DIR}{ch_name.lower()}_{idx}.png"
                if os.path.exists(img_path):
                    s1.image(img_path, use_container_width=True)
                else:
                    s1.warning("Pas d'image")
                
                # Paramètres
                site['url'] = s2.text_input("URL du site", site['url'], key=f"url_{ch_name}_{idx}")
                c1, c2, c3, c4 = s2.columns(4)
                site['zoom'] = c1.number_input("Zoom %", 10, 200, site.get('zoom', 100), key=f"z_{ch_name}_{idx}")
                site['wait_time'] = c2.number_input("Attente (s)", 1, 60, site.get('wait_time', 10), key=f"w_{ch_name}_{idx}")
                site['display_time'] = c3.number_input("Durée (s)", 5, 600, site.get('display_time', 30), key=f"d_{ch_name}_{idx}")
                
                if c4.button("🔑 Login", key=f"log_{ch_name}_{idx}", use_container_width=True):
                    add_log(f"Ouverture session manuelle pour {ch_name}_{idx}")
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{site['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])
                
                if s2.button("🗑️ Retirer ce site", key=f"rm_{ch_name}_{idx}"):
                    data["sites"].pop(idx)
                    save_config(cfg)
                    st.rerun()

            if st.button(f"➕ Ajouter un site à {ch_name.upper()}", key=f"add_s_{ch_name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
                save_config(cfg)
                st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    st.subheader("🚀 Pilotage")
    
    # BOUTON SAUVEGARDER
    if st.button("💾 ENREGISTRER & SYNCHRONISER", type="primary", use_container_width=True):
        with st.spinner("Mise à jour Cloud..."):
            if save_config(cfg, sync_git=True):
                st.success("Configuration sauvegardée et envoyée !")
                time.sleep(1)
                st.rerun()

    st.divider()
    
    # BOUTON CAPTURE
    sel_channels = st.multiselect("Canaux à capturer", list(cfg["channels"].keys()))
    if st.button("📸 LANCER LA CAPTURE", use_container_width=True):
        if sel_channels:
            add_log(f"Démarrage cycle de capture pour : {', '.join(sel_channels)}")
            # Logique de capture simplifiée ici
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
                page = browser.new_page()
                for ch in sel_channels:
                    for i, s in enumerate(cfg["channels"][ch]["sites"]):
                        try:
                            page.goto(s['url'], timeout=60000)
                            page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
                            time.sleep(s['wait_time'])
                            page.screenshot(path=f"{SCREENSHOT_DIR}{ch}_{i}.png")
                            add_log(f"Image {ch}_{i} mise à jour", "SUCCESS")
                        except Exception as e:
                            add_log(f"Erreur {ch}_{i}: {str(e)}", "ERROR")
                browser.close()
            save_config(cfg, sync_git=True)
            st.rerun()

    st.subheader("📟 Console Système")
    log_content = "".join(st.session_state.logs)
    st.markdown(f"<div class='console-box'>{log_content}</div>", unsafe_allow_html=True)
    
    if st.button("🧹 Effacer la console"):
        st.session_state.logs = []
        st.rerun()