import streamlit as st
import json, time, os, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# Configuration
CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

st.set_page_config(page_title="FactoryCast Pro v6", layout="wide")

# Style Schneider / Industriel
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 5px; height: 3em; }
    .log-box { background: #0e1117; color: #00ff41; padding: 15px; font-family: 'Courier New', monospace; font-size: 12px; border-radius: 5px; height: 400px; overflow-y: auto; }
    </style>
    """, unsafe_allow_html=True)

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
            repo.index.commit(f"Update: {datetime.now().strftime('%H:%M:%S')}")
            repo.remote(name='origin').push()
            return True
        except Exception as e:
            st.error(f"Erreur SSH/Git : {e}")
    return False

# --- LOGIQUE DE CAPTURE ---
def run_capture(ch_id, site_idx, site_data):
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        try:
            page.goto(site_data['url'], wait_until="networkidle", timeout=60000)
            page.evaluate(f"document.body.style.zoom = '{site_data['zoom']}%'")
            
            # Scroll pour réveiller les graphs (Node-RED/Dashboards)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, 0)")
            
            # Attente de stabilisation
            time.sleep(site_data['wait_time'])
            
            raw_path = f"{SCREENSHOT_DIR}temp_{ch_id}.png"
            page.screenshot(path=raw_path, full_page=True)
            
            # Traitement des splits
            img = Image.open(raw_path)
            w, h = img.size
            n = site_data.get('split', 1)
            for p_idx in range(n):
                top = p_idx * (h // n)
                bottom = (p_idx + 1) * (h // n) if p_idx < n-1 else h
                part = img.crop((0, top, w, bottom))
                part.save(f"{SCREENSHOT_DIR}{ch_id}_{site_idx}_p{p_idx}.png")
            
            browser.close()
            return True
        except Exception as e:
            print(f"Erreur : {e}")
            browser.close()
            return False

# --- UI STREAMLIT ---
cfg = load_config()

st.title("🏭 FactoryCast Pro v6")

if 'running' not in st.session_state: st.session_state.running = False
if 'logs' not in st.session_state: st.session_state.logs = []

col_cfg, col_run = st.columns([2, 1])

with col_cfg:
    st.subheader("⚙️ Configuration")
    
    # Gestion des canaux
    channels_to_delete = []
    updated_channels = {}
    
    for name, data in cfg["channels"].items():
        with st.expander(f"📍 Point d'affichage : {name}", expanded=True):
            # Option de renommage
            new_name = st.text_input("Nom du point", name, key=f"name_{name}")
            
            for i, site in enumerate(data["sites"]):
                st.markdown(f"**Site #{i}**")
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
                site['url'] = c1.text_input("URL", site['url'], key=f"url{name}{i}")
                site['zoom'] = c2.number_input("Zoom %", 10, 200, site['zoom'], key=f"z{name}{i}")
                site['wait_time'] = c3.number_input("Stabilis.(s)", 0, 100, site['wait_time'], key=f"w{name}{i}")
                site['display_time'] = c4.number_input("Affich.(s)", 5, 3600, site['display_time'], key=f"d{name}{i}")
                site['refresh_freq'] = c5.number_input("MàJ (sec)", 10, 86400, site.get('refresh_freq', 300), key=f"r{name}{i}")
                
                # Split et bouton retirer
                cs1, cs2 = st.columns([1, 4])
                site['split'] = cs1.selectbox("Split", [1, 2, 3], index=site['split']-1, key=f"s{name}{i}")
                if cs2.button(f"🗑️ Retirer Site #{i}", key=f"del_s{name}{i}"):
                    data["sites"].pop(i)
                    save_config(cfg)
                    st.rerun()

            if st.button(f"➕ Ajouter un site à {name}", key=f"add_s{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1, "refresh_freq": 300})
                save_config(cfg); st.rerun()
            
            if st.button(f"❌ Supprimer le point {name}", key=f"del_p{name}"):
                channels_to_delete.append(name)

            # Logique de renommage
            updated_channels[new_name] = data

    for d in channels_to_delete: del updated_channels[d]
    cfg["channels"] = updated_channels

    if st.button("➕ CRÉER UN NOUVEAU POINT D'AFFICHAGE"):
        cfg["channels"][f"nouveau_point_{len(cfg['channels'])+1}"] = {"sites": []}
        save_config(cfg); st.rerun()

    if st.button("💾 ENREGISTRER & SYNCHRONISER SSH", type="primary"):
        save_config(cfg, sync_git=True)
        st.success("Configuration mise à jour et envoyée au Cloud !")

with col_run:
    st.subheader("🚀 Pilotage")
    active_channels = st.multiselect("Canaux à surveiller", list(cfg["channels"].keys()), default=list(cfg["channels"].keys()))
    
    if not st.session_state.running:
        if st.button("▶️ DÉMARRER L'AUTOMATE", use_container_width=True):
            st.session_state.running = True; st.rerun()
    else:
        if st.button("🛑 ARRÊTER", type="secondary", use_container_width=True):
            st.session_state.running = False; st.rerun()
    
    st.markdown("### 📝 Logs")
    log_area = st.empty()
    log_content = "".join([f"<div>{l}</div>" for l in st.session_state.logs])
    log_area.markdown(f"<div class='log-box'>{log_content}</div>", unsafe_allow_html=True)

# --- BOUCLE DE TRAITEMENT ---
if st.session_state.running:
    any_update = False
    for ch in active_channels:
        for idx, site in enumerate(cfg["channels"][ch]["sites"]):
            last = site.get('last_update_ts', 0)
            if (time.time() - last) > site['refresh_freq']:
                st.session_state.logs.insert(0, f"[{datetime.now().strftime('%H:%M')}] MàJ : {ch} Site #{idx}...")
                if run_capture(ch, idx, site):
                    site['last_update_ts'] = time.time()
                    site['last_update_str'] = datetime.now().strftime("%H:%M:%S")
                    any_update = True
    
    if any_update:
        save_config(cfg, sync_git=True)
        st.rerun()
    else:
        time.sleep(10) # Attente avant prochaine vérification
        st.rerun()