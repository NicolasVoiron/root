import streamlit as st
import json, time, os, sys, asyncio, subprocess
from playwright.sync_api import sync_playwright
from git import Repo
from datetime import datetime
from PIL import Image  # Pour le découpage des images

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="FactoryCast Pro | Split Edition", layout="wide")

# --- STYLE ---
st.markdown("""
    <style>
    :root { --se-green: #3dcd58; --se-dark: #3e4042; }
    .stApp { background-color: #ffffff; }
    .channel-card { background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 10px solid var(--se-green); margin-bottom: 20px; border: 1px solid #ddd; }
    .stButton>button { border-radius: 4px; font-weight: bold; }
    .console-box { background: #1e1e1e; color: #d4d4d4; padding: 15px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

CONFIG_FILE = "config.json"
SCREENSHOT_DIR = "docs/screens/"

if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg, level="INFO"):
    t = datetime.now().strftime("%H:%M:%S")
    color = {"INFO": "#fff", "SUCCESS": "#3dcd58", "ERROR": "#f44747", "GIT": "#569cd6"}[level]
    st.session_state.logs.insert(0, f"<div style='color:{color}'>[{t}] {msg}</div>")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {"channels": {}}

def save_config(config, sync=False):
    with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
    if sync:
        try:
            repo = Repo("./")
            repo.git.add(all=True)
            repo.git.add('config.json', force=True)
            repo.index.commit(f"Update FactoryCast: {datetime.now().strftime('%H:%M')}")
            repo.remote(name='origin').push()
            add_log("Synchronisation GitHub réussie (SSH)", "GIT")
        except Exception as e: add_log(f"Erreur Git: {str(e)}", "ERROR")

# --- MOTEUR DE CAPTURE AVEC SPLIT ---
def run_capture_pro(selected_channels):
    cfg = load_config()
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        add_log("Lancement du moteur Schneider...")
        browser = p.chromium.launch_persistent_context(user_data_dir="./browser_session", headless=True)
        page = browser.new_page()
        
        for ch in selected_channels:
            for i, s in enumerate(cfg["channels"][ch]["sites"]):
                try:
                    add_log(f"Capture Full-Page : {s['url']}")
                    page.goto(s['url'], timeout=60000, wait_until="networkidle")
                    page.evaluate(f"document.body.style.zoom = '{s.get('zoom', 100)/100}'")
                    time.sleep(s.get('wait_time', 5))
                    
                    # 1. Capture de la page COMPLETE
                    temp_path = f"{SCREENSHOT_DIR}temp_{ch}_{i}.png"
                    page.screenshot(path=temp_path, full_page=True)
                    
                    # 2. Gestion du SPLIT (Découpage)
                    split_count = s.get('split', 1)
                    img = Image.open(temp_path)
                    width, height = img.size
                    
                    if split_count > 1:
                        part_height = height // split_count
                        for p_idx in range(split_count):
                            top = p_idx * part_height
                            bottom = (p_idx + 1) * part_height if p_idx < split_count - 1 else height
                            part_img = img.crop((0, top, width, bottom))
                            part_img.save(f"{SCREENSHOT_DIR}{ch}_{i}_p{p_idx}.png")
                        add_log(f"Image découpée en {split_count} parties", "SUCCESS")
                    else:
                        img.save(f"{SCREENSHOT_DIR}{ch}_{i}_p0.png")
                    
                    os.remove(temp_path) # Nettoyage
                    add_log(f"Site {i} mis à jour", "SUCCESS")
                except Exception as e: add_log(f"Erreur site {i}: {str(e)}", "ERROR")
        browser.close()
    save_config(cfg, sync=True)

# --- UI ---
st.title("FactoryCast Pro | Schneider Electric")
cfg = load_config()

c1, c2 = st.columns([2, 1])

with c1:
    st.header("⚙️ Configuration")
    # Création Canal
    t1, t2 = st.columns([3,1])
    n_ch = t1.text_input("Nom du nouveau canal", label_visibility="collapsed", placeholder="Nom du canal...")
    if t2.button("➕ Créer"):
        if n_ch: cfg["channels"][n_ch.lower()] = {"sites": []}; save_config(cfg); st.rerun()

    for ch_name, data in cfg["channels"].items():
        with st.container():
            st.markdown(f"<div class='channel-card'>", unsafe_allow_html=True)
            h1, h2 = st.columns([4,1])
            h1.subheader(f"📍 Canal : {ch_name.upper()}")
            if h2.button("🗑️ Supprimer", key=f"d_ch_{ch_name}"):
                del cfg["channels"][ch_name]; save_config(cfg); st.rerun()
            
            # Lien rapide
            url_pub = f"https://nicolasvoiron.github.io/root/index.html?canal={ch_name}"
            st.info(f"🔗 Lien de diffusion : {url_pub}")

            for idx, site in enumerate(data["sites"]):
                st.divider()
                col_m, col_f = st.columns([1, 4])
                
                # Miniature
                m_p = f"{SCREENSHOT_DIR}{ch_name}_{idx}_p0.png"
                if os.path.exists(m_p): col_m.image(m_p)
                
                site['url'] = col_f.text_input("URL", site['url'], key=f"u{ch_name}{idx}")
                r1, r2, r3, r4 = col_f.columns(4)
                site['zoom'] = r1.number_input("Zoom %", 10, 200, site['zoom'], key=f"z{ch_name}{idx}")
                site['display_time'] = r2.number_input("Affichage (s)", 5, 600, site['display_time'], key=f"d{ch_name}{idx}")
                
                # --- NOUVELLE OPTION SPLIT ---
                site['split'] = r3.selectbox("Découpage (Split)", [1, 2, 3], index=site.get('split', 1)-1, key=f"s{ch_name}{idx}")
                
                if r4.button("🔑 Login", key=f"l{ch_name}{idx}"):
                    cmd = f"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch_persistent_context(user_data_dir='./browser_session', headless=False); pg=b.new_page(); pg.goto('{site['url']}'); pg.wait_for_event('close', timeout=0)"
                    subprocess.Popen(["python", "-c", cmd])

            if st.button(f"➕ Ajouter site à {ch_name}", key=f"add_{ch_name}"):
                data["sites"].append({"url": "", "zoom": 100, "wait_time": 5, "display_time": 30, "split": 1})
                save_config(cfg); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.header("🚀 Pilotage")
    if st.button("💾 ENREGISTRER & SYNCHRONISER", type="primary", use_container_width=True):
        save_config(cfg, sync=True)
        st.success("Config synchronisée !")
    
    st.divider()
    sel = st.multiselect("Canaux à capturer", list(cfg["channels"].keys()))
    if st.button("📸 LANCER LA CAPTURE", use_container_width=True):
        run_capture_pro(sel); st.rerun()
    
    st.subheader("📟 Console")
    st.markdown(f"<div class='console-box'>{''.join(st.session_state.logs)}</div>", unsafe_allow_html=True)