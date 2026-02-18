import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# --- CORRECTIF INDISPENSABLE POUR WINDOWS & PYTHON 3.12 ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- CONFIGURATION VISUELLE SCHNEIDER ELECTRIC ---
st.set_page_config(page_title="FactoryCast Elite | Schneider Electric", layout="wide")

st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    h1, h2 { color: var(--se-dark) !important; border-bottom: 3px solid var(--se-green); padding-bottom: 10px; }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; border: none; border-radius: 4px; font-weight: bold; width: 100%; height: 3em; }
    .site-card { border: 1px solid #ddd; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 10px solid var(--se-green); background: #fdfdfd; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .log-box { background: #2b2d2f; color: #00ff41; font-family: 'Consolas', monospace; padding: 15px; height: 350px; overflow-y: auto; border-radius: 5px; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, type="info"):
    t = datetime.now().strftime("%H:%M:%S")
    icon = "✅" if type == "success" else "❌" if type == "error" else "⚙️"
    st.session_state.logs.insert(0, f"[{t}] {icon} {msg}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)

# --- MOTEUR DE CAPTURE PROFESSIONNEL ---
def run_capture_cycle(selected_channels):
    config = load_config()
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Initialisation du navigateur Schneider...")
        # Utilisation d'un contexte persistant pour garder les sessions (logins)
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Analyse du canal : {ch.upper()}")
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                
                try:
                    add_log(f"Accès (Full Page) : {site['url']}")
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    
                    # Application du Zoom
                    zoom = site.get('zoom', 100) / 100
                    page.evaluate(f"document.body.style.zoom = '{zoom}'")
                    
                    time.sleep(site.get('wait_time', 5))
                    
                    # Capture Full Page
                    path = f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png"
                    page.screenshot(path=path, full_page=True)
                    add_log(f"Capture réussie pour {ch}_{i}", "success")
                    
                except Exception as e:
                    add_log(f"Échec sur {site['url']} : {str(e)}", "error")
        browser.close()

    # --- SYNCHRO GITHUB VIA TON SSH ---
    try:
        add_log("Synchronisation SSH avec GitHub...")
        repo = Repo("./")
        
        # On s'assure que Git suit bien le dossier docs
        repo.git.add(all=True) 
        
        commit_msg = f"Update Screens {datetime.now().strftime('%H:%M')}"
        repo.index.commit(commit_msg)
        
        origin = repo.remote(name='origin')
        origin.push()
        add_log("Cloud mis à jour avec succès !", "success")
    except Exception as e:
        add_log(f"Erreur Sync Git : {str(e)}", "error")

# --- UI PRINCIPALE ---
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Schneider_Electric_2007.svg/1200px-Schneider_Electric_2007.svg.png", width=180)
st.title("FactoryCast Control Panel")

c_cfg, c_live = st.columns([1.6, 1])

with c_cfg:
    st.header("⚙️ Configuration des Écrans")
    cfg = load_config()
    
    # Ajout d'un nouveau canal
    with st.expander("➕ Créer un nouveau point d'affichage"):
        n_c = st.text_input("Nom de l'écran (ex: Ateliers)")
        if st.button("Confirmer la création"):
            if n_c: 
                cfg["channels"][n_c.lower()] = {"sites": []}
                save_config(cfg); st.rerun()

    # Liste des canaux
    for name, data in cfg["channels"].items():
        st.subheader(f"📍 Point : {name.upper()}")
        for idx, s in enumerate(data["sites"]):
            with st.container():
                st.markdown("<div class='site-card'>", unsafe_allow_html=True)
                col_info, col_act = st.columns([3, 1])
                
                with col_info:
                    s['active'] = st.toggle("Activer la diffusion", s.get('active', True), key=f"t{name}{idx}")
                    s['url'] = st.text_input("Lien cible", s['url'], key=f"u{name}{idx}")
                    z, w, d = st.columns(3)
                    s['zoom'] = z.number_input("Zoom %", 50, 200, s.get('zoom', 100), 10, key=f"z{name}{idx}")
                    s['wait_time'] = w.number_input("Attente chargement (s)", 1, 120, s['wait_time'], key=f"w{name}{idx}")
                    s['display_time'] = d.number_input("Temps affichage (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")

                with col_act:
                    if st.button("🗑️ Supprimer", key=f"del{name}{idx}"):
                        data["sites"].pop(idx); save_config(cfg); st.rerun()
                    
                    if st.button("🔑 Login Manuel", key=f"log{name}{idx}"):
                        add_log(f"Ouverture session pour {name}...")
                        subprocess.Popen(["python", "-c", f"from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); page = b.new_page(); page.goto('{s['url']}'); print('Fermez le navigateur pour finir'); import time; [time.sleep(1) for _ in range(1000) if b.pages]"])
                
                # Visualisation de la dernière capture
                img_path = f"docs/screens/{name.lower()}_{idx}.png"
                if os.path.exists(img_path):
                    st.image(img_path, caption="Aperçu actuel (Full Page)", width=400)
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        with st.expander(f"➕ Ajouter un site à {name}"):
            a_u = st.text_input("URL du site", key=f"add_u{name}")
            if st.button("Valider l'ajout", key=f"btn_a{name}"):
                if a_u:
                    data["sites"].append({"url": a_u, "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
                    save_config(cfg); st.rerun()

with c_live:
    st.header("🚀 Pilotage Direct")
    
    sel = st.multiselect("Sélectionner les écrans à mettre à jour", list(cfg["channels"].keys()))
    if st.button("▶️ DÉMARRER LA CAPTURE GÉNÉRALE", type="primary", use_container_width=True):
        if sel:
            with st.status("Traitement en cours...", expanded=True) as status:
                run_capture_cycle(sel)
                status.update(label="Cycle terminé !", state="complete")
            st.rerun()
        else: st.error("Sélectionnez au moins un écran.")

    st.divider()
    st.subheader("📟 Console Monitoring")
    logs_html = "<br>".join(st.session_state.logs)
    st.markdown(f"<div class='log-box'>{logs_html}</div>", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("🔗 Liens de diffusion")
    for ch in cfg["channels"]:
        l = f"https://nicolasvoiron.github.io/root/index.html?canal={ch.lower()}"
        st.markdown(f"**{ch.upper()}** : [Ouvrir l'écran]({l})")