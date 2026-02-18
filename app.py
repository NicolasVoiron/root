import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# --- INITIALISATION SYSTÈME ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro | Schneider Electric", layout="wide")

# --- DESIGN SYSTEM SE PRO ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    .main-header { color: var(--se-dark); border-left: 10px solid var(--se-green); padding-left: 15px; }
    .channel-card { background: #fdfdfd; padding: 20px; border-radius: 8px; border: 1px solid #eee; border-top: 4px solid var(--se-green); margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .console-box { background: #121212; color: #00ff41; padding: 15px; height: 450px; overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; border-radius: 4px; line-height: 1.5; }
    .log-step { color: #569cd6; font-weight: bold; }
    .log-success { color: #3dcd58; }
    .log-error { color: #f44747; }
    .log-git { color: #ce9178; }
    .stButton>button { border-radius: 4px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, type="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    styles = {"INFO": "log-step", "SUCCESS": "log-success", "ERROR": "log-error", "GIT": "log-git"}
    icon = {"INFO": "➡️", "SUCCESS": "✅", "ERROR": "❌", "GIT": "☁️"}[type]
    log_entry = f"<div><span style='color:#888'>[{t}]</span> <span class='{styles[type]}'>{icon} {msg}</span></div>"
    st.session_state.logs.insert(0, log_entry)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config, sync_git=False):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
    if sync_git:
        try:
            add_log("Démarrage de la procédure Git...", "GIT")
            repo = Repo("./")
            repo.git.add(all=True)
            repo.git.add('config.json', force=True)
            add_log("Indexation des fichiers terminée", "GIT")
            repo.index.commit(f"Update FactoryCast {datetime.now().strftime('%H:%M')}")
            add_log("Commit créé avec succès", "GIT")
            repo.remote(name='origin').push()
            add_log("Synchronisation SSH GitHub réussie !", "SUCCESS")
        except Exception as e:
            add_log(f"Erreur Git critique : {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE PROFESSIONNEL ---
def run_full_process(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    add_log(f"Lancement du cycle pour {len(selected_channels)} canal/canaux", "INFO")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            add_log(f"ENTRÉE CANAL : {ch.upper()}", "INFO")
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    add_log(f"Navigation vers : {s['url']}")
                    page.goto(s['url'], timeout=60000, wait_until="networkidle")
                    
                    # Zoom
                    add_log(f"Application du zoom : {s['zoom']}%")
                    page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
                    
                    # Wait Time (Temps de rafraîchissement demandé)
                    add_log(f"Attente de rafraîchissement : {s['wait_time']}s...")
                    time.sleep(s['wait_time'])
                    
                    # Capture Full Page
                    temp_p = f"{SCREENSHOT_DIR}raw_{ch}_{i}.png"
                    add_log("Capture de la page complète (Full Page Mode)")
                    page.screenshot(path=temp_p, full_page=True)
                    
                    # Split Logic
                    split_n = s.get('split', 1)
                    img = Image.open(temp_p)
                    w, h = img.size
                    if split_n > 1:
                        add_log(f"Découpage de l'image en {split_n} segments...")
                        segment_h = h // split_n
                        for p_idx in range(split_n):
                            top = p_idx * segment_h
                            bottom = h if p_idx == split_n - 1 else (p_idx + 1) * segment_h
                            img.crop((0, top, w, bottom)).save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                    else:
                        img.save(f"{SCREENSHOT_DIR}{ch}_{i}_p0.png")
                    
                    os.remove(temp_p)
                    add_log(f"Traitement terminé pour {ch}_{i}", "SUCCESS")
                except Exception as e:
                    add_log(f"ÉCHEC sur {ch}_{i} : {str(e)}", "ERROR")
        
        browser.close()
    
    save_config(cfg, sync_git=True)

# --- INTERFACE ---
st.markdown("<h1 class='main-header'>FactoryCast Control Panel Pro</h1>", unsafe_allow_html=True)
cfg = load_config()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📁 Configuration des Canaux")
    # Création
    t1, t2 = st.columns([3,1])
    n_ch = t1.text_input("Nouveau Canal", placeholder="ex: BUREAU_R&D", label_visibility="collapsed")
    if t2.button("➕ CRÉER CANAL", use_container_width=True):
        if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    for name, data in cfg["channels"].items():
        with st.container():
            st.markdown(f"<div class='channel-card'>", unsafe_allow_html=True)
            h1, h2, h3 = st.columns([3, 1.5, 1])
            h1.markdown(f"### 📍 {name.upper()}")
            
            p_url = f"https://nicolasvoiron.github.io/root/index.html?canal={name}"
            h1.markdown(f"🔗 [Lien Public]({p_url})")

            if h3.button("🗑️ Suppr.", key=f"del_ch_{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

            for idx, s in enumerate(data["sites"]):
                st.divider()
                m1, m2 = st.columns([1, 4])
                img_p = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(img_p): m1.image(img_p)
                
                s['url'] = m2.text_input("URL", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4 = m2.columns(4)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Attente (s)", 1, 60, s['wait_time'], key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Affichage (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s.get('split', 1)-1, key=f"s{name}{idx}")
                
                if m2.button(f"🔑 Login Manuel {name}_{idx}"):
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])

            if st.button(f"➕ Ajouter un site à {name.upper()}", key=f"add_{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 10, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.subheader("🚀 Pilotage & Console")
    if st.button("💾 SAUVEGARDER & SYNC GIT", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True); st.success("Synchronisé !")
    
    st.divider()
    sel = st.multiselect("Sélection canaux", list(cfg["channels"].keys()))
    if st.button("▶️ LANCER LA CAPTURE GÉNÉRALE", use_container_width=True):
        if sel: run_full_process(sel); st.rerun()
    
    st.markdown("---")
    st.markdown("📜 **LOGS SYSTÈME DÉTAILLÉS**")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    if st.button("Nettoyer Console"): st.session_state.logs = []; st.rerun()