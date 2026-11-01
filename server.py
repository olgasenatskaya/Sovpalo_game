import os,random,secrets,string,json
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app=FastAPI()
ROOT=Path(__file__).parent
rooms={}
NOUNS='кошка море работа любовь пицца отпуск директор космос дождь праздник робот шоколад дракон телефон лес сон город поезд кофе музыка школа книга солнце луна тайна друг собака кино танец снег океан самолет подарок страх мечта облако торт театр компьютер велосипед парк ребенок художник чемпион магия дерево остров корабль музей завтрак путешествие'.split()
ADJS='ленивая бесконечное сложная вечная горячая страшный веселый волшебный дорогой холодная нежный странный яркий грустный сладкий шумный спокойный быстрый загадочный опасный уютный скучный добрый огромный смешной редкий прекрасный мокрый глупый смелый дикий важный забытый хрупкий тайный неожиданный счастливый древний солнечный дерзкий'.split()
# Adjectives deliberately use mixed genders: association, not grammar, is the challenge.

def code():
 while True:
  c=''.join(random.choices(string.ascii_uppercase+string.digits,k=6))
  if c not in rooms:return c

def new_round(r):
 r['round']+=1;r['nouns']=random.sample(NOUNS,5);r['adjs']=random.sample(ADJS,5);r['answers']={};r['phase']='host';r['host']=r['order'][(r['round']-1)%len(r['order'])]

def snapshot(r,pid):
 return {'type':'state','code':r['code'],'you':pid,'players':[{'id':x,'name':r['names'][x],'score':r['scores'][x]} for x in r['order']],'host':r['host'],'phase':r['phase'],'round':r['round'],'nouns':r['nouns'],'adjs':r['adjs'],'submitted':list(r['answers']),'revealed':r.get('revealed',{}) if r['phase']=='reveal' else None}

async def broadcast(r):
 for pid,ws in list(r['sockets'].items()):
  try:await ws.send_json(snapshot(r,pid))
  except Exception:r['sockets'].pop(pid,None)

@app.get('/')
async def home():return FileResponse(ROOT/'index.html')

@app.websocket('/ws')
async def socket(ws:WebSocket):
 await ws.accept();pid=None;r=None
 try:
  while True:
   m=await ws.receive_json();act=m.get('action')
   if act in ('create','join'):
    name=str(m.get('name','Игрок')).strip()[:24] or 'Игрок';requested=str(m.get('code','')).upper().strip()
    if act=='create':
     c=code();r={'code':c,'names':{},'order':[],'scores':{},'sockets':{},'round':0,'phase':'lobby','nouns':[],'adjs':[],'answers':{},'host':None}
     rooms[c]=r
    else:
     r=rooms.get(requested)
     if not r:await ws.send_json({'type':'error','message':'Комната не найдена'});continue
     if r['phase']!='lobby' and str(m.get('id','')) not in r['names']:await ws.send_json({'type':'error','message':'Раунд уже начался. Подождите следующую игру.'});continue
    old=str(m.get('id',''))
    pid=old if old in r['names'] else secrets.token_urlsafe(12)
    if pid not in r['names']:
     r['names'][pid]=name;r['order'].append(pid);r['scores'][pid]=0
    r['sockets'][pid]=ws
    await broadcast(r)
   elif not r or not pid:await ws.send_json({'type':'error','message':'Сначала войдите в комнату'})
   elif act=='start' and r['phase']=='lobby' and len(r['order'])>=2 and pid==r['order'][0]:new_round(r);await broadcast(r)
   elif act=='submit' and r['phase'] in ('host','guess'):
    values=m.get('mapping')
    if not isinstance(values,list) or sorted(values)!=list(range(5)):continue
    if r['phase']=='host' and pid==r['host']:
     r['answers'][pid]=values;r['phase']='guess'
    elif r['phase']=='guess' and pid!=r['host'] and pid not in r['answers']:r['answers'][pid]=values
    else:continue
    if r['phase']=='guess' and all(x in r['answers'] for x in r['order']):
     host=r['answers'][r['host']];r['revealed']={}
     for x in r['order']:
      if x!=r['host']:
       points=sum(a==b for a,b in zip(host,r['answers'][x]));r['scores'][x]+=points;r['revealed'][x]={'mapping':r['answers'][x],'points':points}
     r['revealed'][r['host']]={'mapping':host,'points':0};r['phase']='reveal'
    await broadcast(r)
   elif act=='next' and r['phase']=='reveal' and pid==r['host']:new_round(r);await broadcast(r)
 except WebSocketDisconnect:pass
 finally:
  if r and pid and r['sockets'].get(pid) is ws:
   r['sockets'].pop(pid,None)
   await broadcast(r)
