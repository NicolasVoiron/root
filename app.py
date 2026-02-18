import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# --- CONFIGURATION INITIALE ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro | Schneider Electric", layout="wide")

# --- DESIGN SYSTEM SCHNEIDER ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; --se-bg: #f4f4f4; }
    .stApp { background-color: white; }
    .main-header { color: var(--se-dark); border-left: 12px solid var(--se-green); padding-left: 20px; margin-bottom: 30px; }
    .channel-card { background: var(--se-bg); padding: 25px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px; position: relative; }
    .stButton>button { border-radius: 4px; font-weight: bold; }
    .console-box { background: #121212; color: #d4d4d4; padding: 15px; height: 400px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 5px; border-top: 4px solid #444; }
    .log-time { color: #888; }
    .log-info { color: #569cd6; }
    .log-success { color: #3dcd58; font-weight: bold; }
    .log-error { color: #f44747; }
    .log-git { color: #ce9178; }
    .link-badge { background: #e8f5e9; color: #2e7d32; padding: 8px 15px; border-radius: 5px; font-weight: bold; text-decoration: none; display: inline-block; margin-top: 10px; border: 1px solid #c8e6c9; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, level="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    style = {"INFO": "log-info", "SUCCESS": "log-success", "ERROR": "log-error", "GIT": "log-git"}[level]
    icon = {"INFO": "➡️", "SUCCESS": "✅", "ERROR": "❌", "GIT": "☁️"}[level]
    log_entry = f"<div><span class='log-time'>[{t}]</span> <span class='{style}'>{icon} {msg}</span></div>"
    st.session_state.logs.insert(0, log_entry)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config, sync_git=False):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
    if sync_git:
        try:
            add_log("Initialisation du tunnel SSH vers GitHub...", "GIT")
            repo = Repo("./")
            repo.git.add(all=True)
            repo.git.add(CONFIG_FILE, force=True)
            add_log("Indexation des fichiers (incluant config.json)", "GIT")
            repo.index.commit(f"FactoryCast Sync: {datetime.now().strftime('%H:%M')}")
            repo.remote(name='origin').push()
            add_log("Synchronisation Cloud réussie !", "SUCCESS")
        except Exception as e: add_log(f"Erreur Git : {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE PRO ---
def capture_cycle(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    add_log(f"Démarrage du cycle pour {len(selected_channels)} canal/canaux", "INFO")
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"Traitement Canal : {ch.upper()}", "INFO")
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    add_log(f"Navigation : {s['url']}")
                    page.goto(s['url'], timeout=60000, wait_until="networkidle")
                    
                    add_log(f"Configuration : Zoom {s['zoom']}%")
                    page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
                    
                    add_log(f"Attente de rafraîchissement (Wait Time) : {s['wait_time']}s")
                    time.sleep(s['wait_time'])
                    
                    # Capture Full Page
                    temp_p = f"{SCREENSHOT_DIR}raw_{ch}_{i}.png"
                    add_log("Capture Full-Page en cours...")
                    page.screenshot(path=temp_p, full_page=True)
                    
                    # Logique de Split (PIL)
                    split_n = s.get('split', 1)
                    img = Image.open(temp_p)
                    w, h = img.size
                    segment_h = h // split_n
                    
                    for p_idx in range(split_n):
                        top = p_idx * segment_h
                        bottom = h if p_idx == split_n - 1 else (p_idx + 1) * segment_h
                        img.crop((0, top, w, bottom)).save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                    
                    if split_n > 1: add_log(f"Découpage réussi : {split_n} colonnes", "INFO")
                    os.remove(temp_p)
                    
                    # Enregistrement heure mise à jour
                    s['last_update'] = datetime.now().strftime("%H:%M:%S")
                    add_log(f"Succès total pour {ch}_{i}", "SUCCESS")
                except Exception as e: add_log(f"Erreur {ch}_{i} : {str(e)}", "ERROR")
        browser.close()
    save_config(cfg, sync_git=True)

# --- INTERFACE UTILISATEUR ---
st.markdown("<h1 class='main-header'>FactoryCast Pro Dashboard</h1>", unsafe_allow_html=True)
cfg = load_config()

c_ui, c_console = st.columns([2, 1])

with c_ui:
    st.subheader("📁 Canaux d'affichage")
    t1, t2 = st.columns([3,1])
    n_ch = t1.text_input("Nouveau Canal", placeholder="Nom du canal...", label_visibility="collapsed")
    if t2.button("➕ CRÉER", use_container_width=True):
        if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        with st.container():
            st.markdown("<div class='channel-card'>", unsafe_allow_html=True)
            h1, h2, h3 = st.columns([3, 1.5, 1])
            h1.markdown(f"### 📍 Point : {name.upper()}")
            
            p_url = f"https://nicolasvoiron.github.io/root/index.html?canal={name}"
            h1.markdown(f"<a href='{p_url}' target='_blank' class='link-badge'>🔗 Lien de diffusion public</a>", unsafe_allow_html=True)

            if h3.button("🗑️ Suppr.", key=f"del_c_{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

            for idx, s in enumerate(data["sites"]):
                st.divider()
                s_col1, s_col2 = st.columns([1, 4])
                
                # Miniature
                m_path = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(m_path): s_col1.image(m_path)
                
                s['url'] = s_col2.text_input("URL Cible", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4 = s_col2.columns(4)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s.get('zoom', 100), key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Attente (s)", 1, 60, s.get('wait_time', 10), key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Affichage (s)", 5, 600, s.get('display_time', 30), key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s.get('split', 1)-1, key=f"s{name}{idx}")
                
                if s_col2.button(f"🔑 Login Manuel ({name}_{idx})", use_container_width=True):
                    add_log(f"Ouverture navigateur pour identification : {name}_{idx}", "INFO")
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])
                
                if s_col2.button("🗑️ Retirer le site", key=f"rm_{name}{idx}"):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter site à {name.upper()}", key=f"add_{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with c_console:
    st.subheader("🚀 Pilotage")
    if st.button("💾 SAUVEGARDER & SYNC CLOUD", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True); st.success("Synchronisé !")
    
    st.divider()
    sel = st.multiselect("Sélectionner canaux", list(cfg["channels"].keys()))
    if st.button("📸 LANCER LA CAPTURE", use_container_width=True):
        if sel: capture_cycle(sel); st.rerun()
    
    st.markdown("---")
    st.markdown("📜 **LOGS SYSTÈME DÉTAILLÉS**")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    if st.button("🧹 Effacer logs"): st.session_state.logs = []; st.rerun()