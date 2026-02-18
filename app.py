import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime

# --- CONFIGURATION UI ---
st.set_page_config(page_title="FactoryCast | Schneider Electric", layout="wide")

st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    h1, h2 { color: var(--se-dark) !important; border-bottom: 3px solid var(--se-green); }
    .stButton>button { background-color: var(--se-green) !important; color: white !important; height: 3em; border-radius: 4px; }
    .log-box { background: #2b2d2f; color: #00ff41; font-family: monospace; padding: 10px; height: 250px; overflow-y: auto; border-radius: 5px; }
    .site-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 10px solid var(--se-green); }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

# Initialisation des logs
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

# --- ENGINE DE CAPTURE (FULL PAGE + ZOOM) ---
def run_capture_cycle(selected_channels):
    config = load_config()
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        add_log("Démarrage du moteur de capture...")
        # Headless=True pour ne pas voir le navigateur s'ouvrir
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Canal : {ch}")
            for i, site in enumerate(config["channels"][ch]["sites"]):
                if not site.get('active', True): continue
                
                try:
                    add_log(f"Capture de {site['url']} (Zoom: {site.get('zoom', 100)}%)")
                    page.goto(site['url'], timeout=60000, wait_until="networkidle")
                    
                    # Application du Zoom et capture Full Page
                    zoom = site.get('zoom', 100) / 100
                    page.evaluate(f"document.body.style.zoom = '{zoom}'")
                    time.sleep(site.get('wait_time', 5))
                    
                    # --- FIX: CAPTURE PAGE COMPLETE ---
                    path = f"{SCREENSHOT_DIR}{ch.lower()}_{i}.png"
                    page.screenshot(path=path, full_page=True) 
                    
                except Exception as e:
                    add_log(f"Erreur : {str(e)}", "error")
        browser.close()

    try:
        repo = Repo("./")
        add_log("Envoi vers GitHub...")
        # On ajoute index.html AU CAS OU il manque
        repo.git.add("index.html")
        repo.git.add("docs/*")
        repo.git.commit('--amend', '-m', 'Sync Screens', '--no-edit')
        repo.git.push('--force')
        add_log("Diffusion à jour !", "success")
    except Exception as e:
        add_log(f"Erreur Git : {str(e)}", "error")

# --- INTERFACE ---
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Schneider_Electric_2007.svg/1200px-Schneider_Electric_2007.svg.png", width=150)
st.title("FactoryCast Control Panel")

col_cfg, col_live = st.columns([1.5, 1])

with col_cfg:
    st.header("⚙️ Configuration")
    cfg = load_config()
    
    # Création canal
    with st.expander("➕ Créer un nouveau point d'affichage"):
        n_c = st.text_input("Nom de l'écran (ex: Bureau, Usine)")
        if st.button("Valider"):
            if n_c: cfg["channels"][n_c] = {"sites": []}; save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        st.subheader(f"📍 Écran : {name.upper()}")
        for idx, s in enumerate(data["sites"]):
            with st.container():
                st.markdown("<div class='site-card'>", unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                
                with c1:
                    s['active'] = st.toggle("Activer", s.get('active', True), key=f"t{name}{idx}")
                    s['url'] = st.text_input("URL", s['url'], key=f"u{name}{idx}")
                    
                    z, w, d = st.columns(3)
                    s['zoom'] = z.number_input("Zoom (%)", 50, 200, s.get('zoom', 100), 10, key=f"z{name}{idx}")
                    s['wait_time'] = w.number_input("Attente (s)", 1, 60, s['wait_time'], key=f"w{name}{idx}")
                    s['display_time'] = d.number_input("Affichage (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")

                with c2:
                    if st.button("🗑️", key=f"del{name}{idx}"):
                        data["sites"].pop(idx); save_config(cfg); st.rerun()
                    
                    # FIX: Connexion manuelle sans bloquer l'UI
                    if st.button("🔑 Login", key=f"l{name}{idx}"):
                        add_log(f"Ouverture session pour {name}...")
                        subprocess.Popen(["python", "-c", f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False)
    page = b.new_page()
    page.goto('{s['url']}')
    while b.pages: p.chromium.launch().wait_for_timeout(1000)
"""])

                st.markdown("</div>", unsafe_allow_html=True)
        
        # Ajout avec pré-configuration
        with st.expander(f"➕ Ajouter un site à {name}"):
            a_u = st.text_input("Lien du site", key=f"au{name}")
            if st.button("Confirmer l'ajout", key=f"ab{name}"):
                if a_u:
                    data["sites"].append({"url": a_u, "zoom": 100, "wait_time": 10, "display_time": 30, "active": True})
                    save_config(cfg); st.rerun()

with col_live:
    st.header("🚀 Pilotage")
    sel = st.multiselect("Choisir les écrans à rafraîchir", list(cfg["channels"].keys()))
    
    if st.button("▶️ DÉMARRER LA CAPTURE", use_container_width=True):
        if sel:
            with st.status("Traitement en cours...", expanded=True) as status:
                run_capture_cycle(sel)
                status.update(label="Terminé !", state="complete")
            st.rerun()
        else: st.error("Sélectionnez un écran.")

    st.divider()
    st.subheader("📟 Monitoring")
    logs_html = "<br>".join(st.session_state.logs)
    st.markdown(f"<div class='log-box'>{logs_html}</div>", unsafe_allow_html=True)