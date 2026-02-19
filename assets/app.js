(function(){
  const qs = new URLSearchParams(location.search);
  const canal = qs.get('canal');
  const stage = document.getElementById('stage');
  const bar = document.getElementById('bar');
  const tsEl = document.getElementById('timestamp');
  const overlay = document.getElementById('overlay');

  if(!canal){
    overlay.classList.remove('hidden');
    overlay.textContent = 'Paramètre manquant : ?canal=...';
    return;
  }

  let playlist = null;
  let index = -1;

  async function fetchPlaylist(){
    const url = `channels/${canal}/playlist.json?v=${Date.now()}`;
    try{
      const res = await fetch(url, {cache:'no-store'});
      if(!res.ok) throw new Error(res.statusText);
      playlist = await res.json();
      overlay.classList.add('hidden');
      const dt = new Date((playlist.generated_at||Date.now())*1000);
      tsEl.textContent = 'Dernière mise à jour : ' + dt.toLocaleString();
      index = -1;
    }catch(e){
      overlay.classList.remove('hidden');
      overlay.textContent = 'Impossible de charger la playlist. Nouvelle tentative dans 15s';
      await new Promise(r=>setTimeout(r,15000));
      return fetchPlaylist();
    }
  }

  function renderSlide(item){
    const slide = document.createElement('div');
    slide.className = 'slide';
    item.segments = item.segments || [];
    for(const seg of item.segments){
      const wrap = document.createElement('div');
      wrap.className = 'segment';
      const img = document.createElement('img');
      img.src = `${seg}?v=${playlist.version}`;
      wrap.appendChild(img);
      slide.appendChild(wrap);
    }
    return slide;
  }

  async function cycle(){
    if(!playlist) await fetchPlaylist();
    index++;
    if(index >= (playlist.items||[]).length){
      await fetchPlaylist();
      index = 0;
    }
    const item = playlist.items[index];
    if(!item){
      await new Promise(r=>setTimeout(r,2000));
      return cycle();
    }

    const slide = renderSlide(item);
    stage.appendChild(slide);
    requestAnimationFrame(()=>{ slide.classList.add('active'); });

    const dur = Math.max(3, Number(item.display_duration||10));
    const started = performance.now();

    function tick(){
      const p = Math.min(1, (performance.now()-started)/(dur*1000));
      bar.style.width = (p*100).toFixed(2)+'%';
      if(p < 1){ requestAnimationFrame(tick); } else { end(); }
    }
    function end(){
      slide.classList.remove('active');
      setTimeout(()=>{ stage.removeChild(slide); cycle(); }, 600);
    }
    requestAnimationFrame(tick);
  }

  cycle();
})();
