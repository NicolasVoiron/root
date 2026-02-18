import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# --- CONFIGURATION INITIALE ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro V3", layout="wide")

# --- STYLE SCHNEIDER & UI ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #f4f4f4; }
    .channel-container { background: white; padding: 15px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 15px; }
    .console-box { background: #1e1e1e; color: #00ff41; padding: 12px; height: 380px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 11px; border-radius: 4px; border-left: 5px solid #555; }
    .log-git { color: #ce9178; } .log-success { color: #3dcd58; font-weight: bold; }
    .stExpander { border: 1px solid #ddd !important; background: white !important; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False

def add_log(msg, level="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    style = {"INFO": "", "SUCCESS": "log-success", "ERROR": "color:#f44747", "GIT": "log-git"}.get(level, "")
    st.session_state.logs.insert(0, f"<div><span style='color:#777'>[{t}]</span> <span class='{style}'>{msg}</span></div>")

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
            repo.git.add(CONFIG_FILE, force=True)
            repo.index.commit(f"Sync FactoryCast: {datetime.now().strftime('%H:%M')}")
            repo.remote(name='origin').push()
            add_log("Synchronisation SSH réussie !", "GIT")
        except Exception as e: add_log(f"Erreur Git: {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE AMÉLIORÉ ---
def run_capture_sequence(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        # Utilisation d'un contexte persistant pour garder les sessions login
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Traitement Canal : {ch.upper()}")
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    # 1. Navigation avec attente de réseau calme
                    page.goto(s['url'], timeout=90000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
                    
                    # 2. WAIT TIME RÉEL (Playwright Native Wait)
                    add_log(f"Attente forcée pour {ch}_{i} : {s['wait_time']}s")
                    page.wait_for_timeout(s['wait_time'] * 1000)
                    
                    # 3. Capture & Split
                    temp_p = f"{SCREENSHOT_DIR}temp.png"
                    page.screenshot(path=temp_p, full_page=True)
                    
                    split_n = s.get('split', 1)
                    img = Image.open(temp_p)
                    w, h = img.size
                    segment_h = h // split_n
                    for p_idx in range(split_n):
                        img.crop((0, p_idx*segment_h, w, (p_idx+1)*segment_h)).save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                    
                    s['last_update'] = datetime.now().strftime("%H:%M:%S")
                    add_log(f"Mise à jour réussie : {ch}_{i}", "SUCCESS")
                except Exception as e: add_log(f"Erreur {ch}_{i}: {str(e)}", "ERROR")
        browser.close()
    save_config(cfg, sync_git=True)

# --- INTERFACE ---
st.title(" Schneider Electric | FactoryCast Pro")
cfg = load_config()

col_main, col_side = st.columns([2, 1])

with col_main:
    st.subheader("🛠️ Configuration des Écrans")
    
    # Création de canal
    with st.expander("➕ Créer un nouveau point d'affichage"):
        t1, t2 = st.columns([3,1])
        n_ch = t1.text_input("Nom de l'écran (ex: Ateliers)", key="new_ch_name")
        if t2.button("Confirmer la création"):
            if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    # Liste des canaux (Points)
    for name, data in cfg["channels"].items():
        # UTILISATION DE EXPANDER POUR MASQUER / GAINER DE LA PLACE
        with st.expander(f"📍 Point : {name.upper()}", expanded=True):
            st.info(f"🔗 [Lien Public](https://nicolasvoiron.github.io/root/index.html?canal={name})")
            
            for idx, s in enumerate(data["sites"]):
                st.markdown(f"**Site #{idx+1}**")
                s1, s2 = st.columns([1, 4])
                img_p = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(img_p): s1.image(img_p)
                
                s['url'] = s2.text_input("Lien cible", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4 = s2.columns(4)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Attente chargement (s)", 1, 120, s['wait_time'], key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Temps affichage (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s['split']-1, key=f"s{name}{idx}")
                
                b1, b2, b3 = s2.columns(3)
                if b1.button(f"🔑 Login Manuel", key=f"log{name}{idx}"):
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])
                if b2.button(f"🗑️ Retirer", key=f"rm{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter un site à {name}", key=f"add{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            
            if st.button(f"❌ Supprimer le point {name.upper()}", key=f"del{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

    # BOUTON ENREGISTRER GLOBAL
    st.divider()
    if st.button("💾 SAUVEGARDER LA CONFIGURATION", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True)
        st.success("Configuration enregistrée et synchronisée.")

with col_side:
    st.subheader("🚀 Pilotage Direct")
    freq = st.slider("Fréquence de mise à jour (minutes)", 1, 60, 5)
    sel = st.multiselect("Sélectionner les écrans à mettre à jour", list(cfg["channels"].keys()))
    
    if not st.session_state.is_running:
        if st.button("▶️ DÉMARRER LA CAPTURE GÉNÉRALE", type="primary", use_container_width=True):
            if sel:
                st.session_state.is_running = True
                st.rerun()
            else: st.error("Sélectionnez au moins un canal.")
    else:
        if st.button("🛑 ARRÊTER L'AUTO-PILOT", use_container_width=True):
            st.session_state.is_running = False
            st.rerun()
        st.info("🔄 Auto-Pilot Actif. Ne fermez pas cette page.")

    # LA CONSOLE EST PLACÉE ICI POUR RESTER VISIBLE
    st.markdown("### 📟 Console Monitoring")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    if st.button("🧹 Effacer la console"): st.session_state.logs = []; st.rerun()

# --- LOGIQUE DE BOUCLE AUTO-PILOT ---
if st.session_state.is_running:
    run_capture_sequence(sel)
    add_log(f"Cycle terminé. Attente de {freq} minute(s)...")
    time.sleep(freq * 60)
    st.rerun()