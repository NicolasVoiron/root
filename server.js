const express = require('express');
const fs = require('fs');
const fse = require('fs-extra');
const path = require('path');
const ghpages = require('gh-pages');
const { chromium } = require('playwright');
const crypto = require('crypto');

const app = express();
const PORT = 3000;

const ROOT = __dirname;
const ADMIN = path.join(ROOT,'admin');
const WORK = path.join(ROOT,'work/images');
const DIST = path.join(ROOT,'dist');
const DIST_IMG = path.join(DIST,'images');

const TARGETS = path.join(ROOT,'targets.json');
const CREDS = path.join(ROOT,'credentials.json');
const SETTINGS = path.join(ROOT,'settings.json');

for (const d of [WORK, DIST_IMG]) fse.ensureDirSync(d);

if (!fs.existsSync(TARGETS)) fs.writeFileSync(TARGETS,'[]');
if (!fs.existsSync(CREDS)) fs.writeFileSync(CREDS,'{}');
if (!fs.existsSync(SETTINGS)) fs.writeFileSync(SETTINGS, JSON.stringify({repo:'', publicBaseUrl:''},null,2));

app.use(express.json());
app.use('/admin', express.static(ADMIN));
app.use('/public', express.static(DIST));

function read(file){return JSON.parse(fs.readFileSync(file,'utf8'))}
function write(file,data){fs.writeFileSync(file, JSON.stringify(data,null,2))}

app.get('/api/state',(req,res)=>{
  res.json({
    targets: read(TARGETS),
    settings: read(SETTINGS)
  })
});

app.post('/api/settings',(req,res)=>{
  write(SETTINGS, req.body);
  res.json({ok:true});
});

app.post('/api/targets',(req,res)=>{
  const list = read(TARGETS);
  list.push({id: crypto.randomUUID(), ...req.body});
  write(TARGETS, list);
  res.json({ok:true});
});

app.delete('/api/targets/:id',(req,res)=>{
  const list = read(TARGETS).filter(t=>t.id!==req.params.id);
  write(TARGETS, list);
  res.json({ok:true});
});

app.post('/api/publish', async (req,res)=>{
  const settings = read(SETTINGS);
  if (!settings.repo) return res.status(400).json({error:'Repo manquant'});

  const targets = read(TARGETS);
  const items = [];

  for (const t of targets){
    const src = path.join(WORK, t.id+'.png');
    if (fs.existsSync(src)){
      fse.copyFileSync(src, path.join(DIST_IMG, t.id+'.png'));
      items.push({file:'images/'+t.id+'.png', durationSec:t.durationSec||15});
    }
  }

  fs.writeFileSync(path.join(DIST,'latest.json'), JSON.stringify({items},null,2));

  await new Promise((ok,ko)=>{
    ghpages.publish(DIST,{repo:settings.repo,branch:'gh-pages',add:false,history:false},err=>err?ko(err):ok());
  });

  res.json({ok:true});
});

app.post('/api/capture/:id', async (req,res)=>{
  const targets = read(TARGETS);
  const t = targets.find(x=>x.id===req.params.id);
  if (!t) return res.sendStatus(404);

  const browser = await chromium.launch();
  const page = await browser.newPage({viewport:{width:1920,height:1080}});
  await page.goto(t.url,{waitUntil:'domcontentloaded'});
  await page.screenshot({path:path.join(WORK,t.id+'.png'), fullPage:true});
  await browser.close();

  res.json({ok:true});
});

app.listen(PORT,()=>console.log('Admin sur http://localhost:3000/admin'));
