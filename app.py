import streamlit as st
import json, time, os, sys, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image

# --- CONFIGURATION SYSTÈME ---
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro v5 | Schneider Electric", layout="wide")

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

# Design System Schneider
st.markdown("""
    <style>
    .stApp { background-color: #f4f4f4; }
    .console-box { background: #121212; color: #00ff41; padding: 15px; height: 500px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 11px; border-radius: 4px; border-top: 3px solid #555; }
    .stExpander { background: white !important; border-radius: 8px !important; border: 1px solid #ddd !important; margin-bottom: 10px; }
    .log-time { color: #888; } .log-wait { color: #ce9178; } .log-success { color: #3dcd58; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False

def add_log(msg, type="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    color = {"STEP": "#569cd6", "WAIT": "#ce9178", "SUCCESS": "#3dcd58", "ERROR": "#f44747"}.get(type, "#fff")
    st.session_state.logs.insert(0, f"<div><span class='log-time'>[{t}]</span> <span style='color:{color}'>{msg}</span></div>")

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
            repo.index.commit(f"Sync FactoryCast: {datetime.now().strftime('%H:%M:%S')}")
            repo.remote(name='origin').push()
            add_log("Synchronisation Cloud OK (SSH)", "SUCCESS")
        except Exception as e: add_log(f"Erreur Git: {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE ---
def execute_capture(page, ch, idx, s):
    try:
        add_log(f"Navigation : {s['url']}", "STEP")
        page.goto(s['url'], timeout=90000, wait_until="networkidle")
        
        # Action de Zoom CSS (le plus stable)
        page.evaluate(f"document.body.style.zoom = '{s['zoom']/100}'")
        
        # FIX : Réveil des graphiques (Scroll bas puis haut)
        add_log("Activation des composants bas de page...", "STEP")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")

        # WAIT TIME INTERACTIF
        for r in range(s['wait_time'], 0, -5):
            add_log(f"Stabilisation {ch}_{idx} : {r}s restantes...", "WAIT")
            time.sleep(min(5, r))

        # CAPTURE FULL PAGE
        temp_p = f"{SCREENSHOT_DIR}raw.png"
        page.screenshot(path=temp_p, full_page=True)
        
        # SPLIT LOGIC
        img = Image.open(temp_p)
        w, h = img.size
        split_n = s.get('split', 1)
        seg_h = h // split_n
        for p in range(split_n):
            img.crop((0, p*seg_h, w, (p+1)*seg_h if p < split_n-1 else h)).save(f"{SCREENSHOT_DIR}{ch}_{idx}_p{p}.png")
        
        s['last_update_time'] = time.time()
        s['last_update_str'] = datetime.now().strftime("%H:%M:%S")
        add_log(f"Site {ch}_{idx} mis à jour", "SUCCESS")
        return True
    except Exception as e:
        add_log(f"Erreur sur {ch}_{idx} : {str(e)}", "ERROR")
        return False

# --- INTERFACE UTILISATEUR ---
cfg = load_config()
st.title("🏭 FactoryCast Pro v5")

c_left, c_right = st.columns([2, 1])

with c_left:
    st.subheader("🛠️ Configuration des Canaux")
    for name, data in cfg["channels"].items():
        with st.expander(f"📍 POINT : {name.upper()}", expanded=True):
            st.info(f"🔗 [Lien de diffusion](https://nicolasvoiron.github.io/root/index.html?canal={name})")
            
            for idx, s in enumerate(data["sites"]):
                st.markdown(f"**Site #{idx}**")
                s_col1, s_col2 = st.columns([1, 4])
                
                prev = f"{SCREENSHOT_DIR}{name}_{idx}_p0.png"
                if os.path.exists(prev): s_col1.image(prev)
                
                s['url'] = s_col2.text_input("URL", s['url'], key=f"u{name}{idx}")
                r1, r2, r3, r4, r5 = s_col2.columns(5)
                s['zoom'] = r1.number_input("Zoom %", 10, 200, s['zoom'], key=f"z{name}{idx}")
                s['wait_time'] = r2.number_input("Wait (s)", 1, 180, s['wait_time'], key=f"w{name}{idx}")
                s['display_time'] = r3.number_input("Show (s)", 5, 600, s['display_time'], key=f"d{name}{idx}")
                s['split'] = r4.selectbox("Split", [1, 2, 3], index=s['split']-1, key=f"s{name}{idx}")
                s['refresh_freq'] = r5.number_input("MàJ (min)", 1, 1440, s.get('refresh_freq', 5), key=f"f{name}{idx}")
                
                b1, b2 = s_col2.columns(2)
                if b1.button(f"🔑 Login Manuel {name}_{idx}", use_container_width=True):
                    subprocess.Popen(["python", "-c", f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{s['url']}'); pg.wait_for_event('close', timeout=0)"])
                if b2.button(f"🗑️ Retirer", key=f"rm{name}{idx}", use_container_width=True):
                    data["sites"].pop(idx); save_config(cfg); st.rerun()

            if st.button(f"➕ Ajouter un site à {name}", key=f"add{name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 15, "display_time": 30, "split": 1, "refresh_freq": 10})
                save_config(cfg); st.rerun()
            if st.button(f"❌ Supprimer le point {name}", key=f"del{name}"):
                del cfg["channels"][name]; save_config(cfg); st.rerun()

    if st.button("➕ CRÉER UN NOUVEAU POINT D'AFFICHAGE"):
        new_n = f"point_{len(cfg['channels'])+1}"
        cfg["channels"][new_n] = {"sites": []}; save_config(cfg); st.rerun()

    st.divider()
    if st.button("💾 ENREGISTRER & FORCER LA SYNCHRO CLOUD", type="primary", use_container_width=True):
        save_config(cfg, sync_git=True); st.success("Configuration sauvegardée !")

with c_right:
    st.subheader("🚀 Pilotage Auto")
    sel = st.multiselect("Canaux actifs", list(cfg["channels"].keys()), default=list(cfg["channels"].keys()))
    
    if not st.session_state.is_running:
        if st.button("▶️ DÉMARRER L'AUTOMATE", type="primary", use_container_width=True):
            st.session_state.is_running = True; st.rerun()
    else:
        if st.button("🛑 ARRÊTER", type="secondary", use_container_width=True):
            st.session_state.is_running = False; st.rerun()
        st.warning("🔄 Automate en cours de cycle...")

    st.markdown("### 📋 Console de Monitoring")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)
    if st.button("🧹 Effacer logs"): st.session_state.logs = []; st.rerun()

# --- BOUCLE DE TRAITEMENT ---
if st.session_state.is_running:
    need_push = False
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True, viewport={'width': 1920, 'height': 1080})
        page = browser.new_page()
        for ch in sel:
            for i, site in enumerate(cfg["channels"][ch]["sites"]):
                # Check timer individuel
                last = site.get('last_update_time', 0)
                if (time.time() - last) > (site['refresh_freq'] * 60):
                    add_log(f"Cycle de mise à jour pour {ch}_{i}...", "STEP")
                    if execute_capture(page, ch, i, site): need_push = True
        browser.close()
    
    if need_push: save_config(cfg, sync_git=True)
    time.sleep(30) # Vérifie toutes les 30s si un site doit être rafraîchi
    st.rerun()