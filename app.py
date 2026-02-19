import streamlit as st
import time, json, os, subprocess, asyncio
from datetime import datetime
from playwright.sync_api import sync_playwright
from PIL import Image

# --- CONFIGURATION SYSTÈME & STYLE ---
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro v6", layout="wide")
SC_GREEN, SC_DARK = "#3dcd58", "#333333"

st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8f9fa; }}
    .main-title {{ color: {SC_DARK}; border-left: 8px solid {SC_GREEN}; padding-left: 15px; margin-bottom: 30px; }}
    .card {{ background: white; padding: 20px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; border-top: 3px solid {SC_GREEN}; }}
    .stButton>button {{ background-color: {SC_GREEN}; color: white; border-radius: 0; width: 100%; }}
    .console {{ background-color: #1e1e1e; color: #00ff00; font-family: 'Courier New'; padding: 10px; height: 300px; overflow-y: auto; border-radius: 4px; }}
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
DATA_DIR = "displays"
os.makedirs(DATA_DIR, exist_ok=True)

# Chargement Config
if 'config' not in st.session_state:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: st.session_state.config = json.load(f)
    else:
        st.session_state.config = {}

def save_config():
    with open(CONFIG_FILE, 'w') as f: json.dump(st.session_state.config, f, indent=4)

def log_message(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if 'logs' not in st.session_state: st.session_state.logs = []
    st.session_state.logs.append(f"[{timestamp}] {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs.pop(0)

# --- MOTEUR DE CAPTURE ---
def capture_engine(canal):
    with sync_playwright() as p:
        browser_context = p.chromium.launch_persistent_context(
            f"user_data/{canal}", headless=True, viewport={'width': 1920, 'height': 1080}
        )
        page = browser_context.new_page()
        
        for idx, site in enumerate(st.session_state.config[canal]['sites']):
            now = time.time()
            last_upd = site.get('last_ts', 0)
            
            if (now - last_upd) >= int(site['freq']):
                log_message(f"📸 Capture Canal {canal} | Site {idx}...")
                page.goto(site['url'], wait_until="networkidle")
                page.set_viewport_size({"width": 1920, "height": 1080})
                page.evaluate(f"document.body.style.zoom = '{site['zoom']}%'")
                
                time.sleep(int(site['wait_time']))
                
                # Scroll "Réveil" (Bas puis Haut)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                page.evaluate("window.scrollTo(0, 0)")
                
                path = f"{DATA_DIR}/{canal}_{idx}.png"
                page.screenshot(path=path, full_page=True)
                
                # Split Logic (1, 2 ou 3 segments)
                segments = int(site['split'])
                if segments > 1:
                    img = Image.open(path)
                    w, h = img.size
                    for i in range(segments):
                        part = img.crop((0, (h/segments)*i, w, (h/segments)*(i+1)))
                        part.save(f"{DATA_DIR}/{canal}_{idx}_p{i}.png")
                
                site['last_ts'] = now
                site['last_update_str'] = datetime.now().strftime("%H:%M")
        
        browser_context.close()
    
    # Sync Git SSH (Utilise ta config déjà en place)
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-Update {canal}"], check=False)
        subprocess.run(["git", "push"], check=True)
        log_message("✅ Synchro GitHub SSH réussie.")
    except Exception as e:
        log_message(f"❌ Erreur Git : {e}")

# --- INTERFACE SINGLE PAGE ---
st.markdown("<h1 class='main-title'>FACTORYCAST PRO <span style='color:#777'>v6</span></h1>", unsafe_allow_html=True)

col_ctrl, col_monit = st.columns([2, 1])

with col_ctrl:
    # Gestion des Points (Canaux)
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        new_name = c1.text_input("Nom du nouveau point d'affichage", placeholder="Ex: ATELIER_USINAGE")
        if c2.button("Créer Point"):
            if new_name:
                st.session_state.config[new_name] = {"sites": []}
                save_config() ; st.rerun()

        for canal_name in list(st.session_state.config.keys()):
            with st.expander(f"⚙️ Configuration : {canal_name}", expanded=True):
                # Renommage
                new_title = st.text_input("Renommer le point", canal_name, key=f"ren_{canal_name}")
                if new_title != canal_name:
                    st.session_state.config[new_title] = st.session_state.config.pop(canal_name)
                    save_config() ; st.rerun()
                
                st.info(f"🔗 URL TV : `index.html?canal={canal_name}`")
                
                for idx, s in enumerate(st.session_state.config[canal_name]['sites']):
                    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns([3,1,1,1,1,0.5])
                    s['url'] = col_s1.text_input("URL", s['url'], key=f"u{canal_name}{idx}")
                    s['zoom'] = col_s2.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{canal_name}{idx}")
                    s['wait_time'] = col_s3.number_input("Stabil. (s)", 0, 60, s['wait_time'], key=f"w{canal_name}{idx}")
                    s['freq'] = col_s4.number_input("MàJ (s)", 30, 3600, s['freq'], key=f"f{canal_name}{idx}")
                    s['duration'] = col_s5.number_input("Affich. (s)", 5, 600, s['duration'], key=f"d{canal_name}{idx}")
                    s['split'] = st.selectbox("Split", [1,2,3], index=s['split']-1, key=f"sp{canal_name}{idx}")
                    if col_s6.button("🗑️", key=f"del{canal_name}{idx}"):
                        st.session_state.config[canal_name]['sites'].pop(idx)
                        save_config() ; st.rerun()
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button(f"➕ Ajouter Site à {canal_name}"):
                    st.session_state.config[canal_name]['sites'].append({"url": "", "zoom": 100, "wait_time": 5, "freq": 300, "duration": 15, "split": 1})
                    save_config() ; st.rerun()
                
                if col_btn2.button(f"🔐 Login Manuel ({canal_name})"):
                    with sync_playwright() as p:
                        browser = p.chromium.launch_persistent_context(f"user_data/{canal_name}", headless=False)
                        page = browser.new_page()
                        st.warning("Authentifiez-vous puis fermez le navigateur.")
                        while len(browser.pages) > 0: time.sleep(1)
        st.markdown("</div>", unsafe_allow_html=True)

with col_monit:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🚀 AUTO-PILOT")
    if st.button("DEMARRER L'AUTOMATE", type="primary"):
        save_config()
        while True:
            for c in st.session_state.config:
                capture_engine(c)
            time.sleep(10) # Petite pause boucle
            st.rerun()
    
    st.markdown("### 📝 CONSOLE LIVE")
    log_area = st.empty()
    logs = "\n".join(st.session_state.get('logs', ["En attente de démarrage..."]))
    log_area.markdown(f"<div class='console'>{logs}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)