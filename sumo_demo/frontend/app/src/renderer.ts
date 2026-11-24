/**
 * renderer.ts – Ports buildStatic() and render() from lifelane_demo.html to TypeScript.
 * This module only touches canvas; no React state.
 */
import { X, END as _END, ER_X, HALF, BOX, STOPOFF, SIDE as _SIDE, WORLD, APPR as _APPR, MODE_COL, SIG_COL } from './mock/MockSource';
import type { Snapshot } from './types';

const SC = 5; // px per metre for static layer
const MIC = 190;

function mulberry(a: number): () => number {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildStatic(): HTMLCanvasElement {
  const W = Math.ceil((WORLD.x1 - WORLD.x0) * SC);
  const H = Math.ceil((WORLD.y1 - WORLD.y0) * SC);
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d')!;
  g.scale(SC, SC); g.translate(-WORLD.x0, -WORLD.y0);
  const r = mulberry(7);
  const rr = (x: number, y: number, w: number, h: number, rad: number) => {
    g.beginPath(); g.roundRect(x, y, w, h, rad);
  };

  g.fillStyle = '#0b1220'; g.fillRect(WORLD.x0, WORLD.y0, WORLD.x1 - WORLD.x0, WORLD.y1 - WORLD.y0);

  // ---- blocks
  const cols: [number, number][] = [[WORLD.x0, X[0] - 10], [X[0] + 10, X[1] - 10], [X[1] + 10, X[2] - 10], [X[2] + 10, WORLD.x1]];
  const rows: [number, number][] = [[WORLD.y0, -12], [12, WORLD.y1]];
  const pal = ['#18253f','#1b2a47','#16233b','#1e2e4d','#14203a','#22345a'];
  const trees: [number, number, number][] = [];

  rows.forEach((ry, ri) => cols.forEach((cx, ci) => {
    const [x0, x1] = cx, [y0, y1] = ry;
    g.fillStyle = '#16223a'; rr(x0+0.5, y0+0.5, x1-x0-1, y1-y0-1, 3); g.fill();
    const isHosp = ri === 1 && ci === 3, isPark = (ri===1 && ci===1) || (ri===0 && ci===2);
    g.fillStyle = isPark ? '#0f2a1f' : '#111b30'; rr(x0+3, y0+3, x1-x0-6, y1-y0-6, 2); g.fill();
    if (isPark) {
      for (let i = 0; i < 46; i++) trees.push([x0+8+r()*(x1-x0-16), (ri?y0+10:y0+10)+r()*(y1-y0-24), 2.6+r()*2.2]);
      g.strokeStyle='#1d3b2f'; g.lineWidth=1.6; g.beginPath();
      g.moveTo(x0+6, ri?y0+20:y1-20); g.bezierCurveTo(x0+40, ri?y0+60:y1-70, x1-40, ri?y0+30:y1-30, x1-6, ri?y0+70:y1-80); g.stroke();
      return;
    }
    if (isHosp) return;
    const bw=17, bh=15;
    for (let by=y0+7; by+bh<y1-6; by+=bh+6) {
      for (let bx=x0+7; bx+10<x1-6; bx+=bw+5+r()*6) {
        if (r()<0.12) { trees.push([bx+5, by+6, 3+r()*2]); continue; }
        const w=Math.min(bw+r()*8, x1-6-bx), h=bh-1+r()*4;
        g.fillStyle='rgba(0,0,0,.35)'; rr(bx+1.2, by+1.4, w, h, 1.2); g.fill();
        g.fillStyle=pal[Math.floor(r()*pal.length)]; rr(bx, by, w, h, 1.2); g.fill();
        g.strokeStyle='#2b4068'; g.lineWidth=0.28; rr(bx, by, w, h, 1.2); g.stroke();
        for (let wy=by+2; wy<by+h-1.5; wy+=2.6) for (let wx=bx+2; wx<bx+w-1.5; wx+=2.6)
          if (r()<0.38) { g.fillStyle=r()<0.7?'rgba(253,224,130,.55)':'rgba(125,211,252,.45)'; g.fillRect(wx, wy, 1.2, 0.9); }
      }
    }
  }));

  // ---- hospital
  {
    const hx=500, hy=40;
    g.fillStyle='rgba(0,0,0,.45)'; rr(hx+2, hy+2.5, 110, 62, 3); g.fill();
    g.fillStyle='#dbe7f5'; rr(hx, hy, 110, 62, 3); g.fill();
    g.fillStyle='#c3d3e8'; rr(hx+6, hy+6, 44, 50, 2); g.fill(); rr(hx+60, hy+6, 44, 50, 2); g.fill();
    g.fillStyle='#ef4444'; g.fillRect(hx+53, hy+22, 4, 18); g.fillRect(hx+46, hy+29, 18, 4);
    g.fillStyle='#0b1220'; g.font='700 4.5px system-ui'; g.textAlign='center'; g.fillText('CITY HOSPITAL', hx+55, hy+54);
    g.fillStyle='#22c55e'; rr(ER_X-5, 12, 10, 28, 1.5); g.fill();
    g.fillStyle='#ffffff'; g.font='800 4px system-ui'; g.save(); g.translate(ER_X+1.5, 26); g.rotate(-Math.PI/2); g.fillText('EMERGENCY', 0, 0); g.restore();
    g.fillStyle='#16223a'; g.beginPath(); g.arc(640, 76, 14, 0, 7); g.fill();
    g.strokeStyle='#f59e0b'; g.lineWidth=0.9; g.beginPath(); g.arc(640, 76, 11, 0, 7); g.stroke();
    g.fillStyle='#f59e0b'; g.font='800 12px system-ui'; g.fillText('H', 640, 80.4);
  }

  // ---- roads
  const sidewalk='#1a2641', asphalt='#222c42', boxc='#26314a';
  g.fillStyle=sidewalk; g.fillRect(WORLD.x0, -HALF-3, WORLD.x1-WORLD.x0, 2*HALF+6);
  X.forEach(x => g.fillRect(x-BOX-3, WORLD.y0, 2*BOX+6, WORLD.y1-WORLD.y0));
  g.fillStyle=asphalt; g.fillRect(WORLD.x0, -HALF, WORLD.x1-WORLD.x0, 2*HALF);
  X.forEach(x => g.fillRect(x-BOX, WORLD.y0, 2*BOX, WORLD.y1-WORLD.y0));
  g.fillStyle=boxc; X.forEach(x => g.fillRect(x-BOX, -HALF, 2*BOX, 2*HALF));
  g.strokeStyle='#3a4c72'; g.lineWidth=0.3;
  g.beginPath(); g.moveTo(WORLD.x0, -HALF); g.lineTo(WORLD.x1, -HALF);
  g.moveTo(WORLD.x0, HALF); g.lineTo(WORLD.x1, HALF); g.stroke();

  // ---- markings
  const inBox = (x: number) => X.some(j => x > j-14 && x < j+14);
  g.lineWidth=0.35;
  for (let x=WORLD.x0; x<WORLD.x1; x+=1) {
    if (inBox(x)) continue;
    g.fillStyle='#d9a43a'; g.fillRect(x, -0.9, 1.05, 0.28); g.fillRect(x, 0.62, 1.05, 0.28);
  }
  g.strokeStyle='rgba(255,255,255,.55)'; g.setLineDash([3,4]);
  for (const y of [-5.25, 5.25]) {
    g.beginPath();
    let x=WORLD.x0;
    while (x < WORLD.x1) {
      const e = X.find(j => x >= j-14-7 && x < j+14);
      if (e !== undefined) { x=e+14; g.moveTo(x,y); continue; }
      g.moveTo(x,y); g.lineTo(Math.min(x+40,WORLD.x1),y); x+=40;
    }
    g.stroke();
  }
  g.setLineDash([]);
  X.forEach(x => {
    g.fillStyle='#d9a43a';
    for (let y=WORLD.y0; y<WORLD.y1; y+=1) { if (Math.abs(y)<14) continue; g.fillRect(x-0.9, y, 0.28, 1.05); g.fillRect(x+0.62, y, 0.28, 1.05); }
    g.fillStyle='rgba(235,242,255,.85)';
    for (let k=0; k<6; k++) { const o=-HALF+1+k*2.9; [x-11, x+8].forEach(zx=>g.fillRect(zx,o,3,1.5)); }
    for (let k=0; k<4; k++) { const o=x-BOX+1+k*3.5; [-11,8.2].forEach(zy=>g.fillRect(o,zy,1.8,3)); }
    g.fillRect(x-STOPOFF-0.2, 1.75, 0.7, 7); g.fillRect(x+STOPOFF-0.5, -8.75, 0.7, 7);
    g.fillRect(x-5.25, -STOPOFF-0.5, 3.5, 0.7); g.fillRect(x+1.75, STOPOFF-0.2, 3.5, 0.7);
  });
  g.fillStyle='rgba(56,189,248,.08)'; g.fillRect(WORLD.x0, 1.75, WORLD.x1-WORLD.x0, 3.5);
  g.fillStyle='rgba(255,255,255,.28)';
  [60,200,380,540].forEach(x => { [[7,1],[3.5,1],[-7,-1]].forEach(([y,d]) => { g.beginPath(); g.moveTo(x+3*d,y); g.lineTo(x-1*d,y-1.2); g.lineTo(x-1*d,y+1.2); g.fill(); }); });

  // ---- trees
  X.forEach((x, i) => {
    for (let tx=WORLD.x0+8; tx<WORLD.x1; tx+=17) { if (Math.abs(tx-x)<20) continue; if (i===0) { trees.push([tx,-HALF-1.6,1.5],[tx+6,HALF+1.6,1.5]); } }
  });
  trees.forEach(([tx,ty,rad]) => {
    g.fillStyle='rgba(0,0,0,.3)'; g.beginPath(); g.arc(tx+0.8,ty+0.9,rad,0,7); g.fill();
    g.fillStyle=r()<0.5?'#14532d':'#166534'; g.beginPath(); g.arc(tx,ty,rad,0,7); g.fill();
    g.fillStyle='rgba(134,239,172,.25)'; g.beginPath(); g.arc(tx-rad*.25,ty-rad*.3,rad*.55,0,7); g.fill();
  });
  return c;
}

// ---- Camera state ----
export interface Camera { x: number; y: number; z: number; follow: boolean; }

function lamp(ctx: CanvasRenderingContext2D, x: number, y: number, st: string, dpr: number) {
  ctx.fillStyle='#0b1220'; ctx.beginPath(); ctx.roundRect(x-1.5,y-4.3,3,8.6,1); ctx.fill();
  ctx.strokeStyle='#33466e'; ctx.lineWidth=0.25; ctx.stroke();
  for (const [k,dy] of [['R',-2.8],['Y',0],['G',2.8]] as [string,number][]) {
    const on=st===k; ctx.fillStyle=on?SIG_COL[k]:'#1b2740';
    if (on) { ctx.shadowColor=SIG_COL[k]; ctx.shadowBlur=10*dpr; }
    ctx.beginPath(); ctx.arc(x, y+dy, 0.95, 0, 7); ctx.fill(); ctx.shadowBlur=0;
  }
}

function bar(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, st: string, dpr: number) {
  ctx.fillStyle=SIG_COL[st]; ctx.shadowColor=SIG_COL[st]; ctx.shadowBlur=9*dpr;
  ctx.globalAlpha=st==='R'?0.75:1; ctx.fillRect(x,y,w,h); ctx.globalAlpha=1; ctx.shadowBlur=0;
}

function fitZoom(cv: HTMLCanvasElement, dpr: number): number {
  return Math.min(cv.width/dpr/700, cv.height/dpr/262);
}

export function render(
  snapshot: Snapshot,
  now: number,
  cam: Camera,
  staticCanvas: HTMLCanvasElement,
  cv: HTMLCanvasElement,
  ctx: CanvasRenderingContext2D,
  dpr: number,
) {
  const t = now / 1000;
  const A = snapshot.ambulance;
  const ambVeh = snapshot.vehicles.find(v => v.kind === 'ambulance') ?? null;

  // Camera lerp
  const fz = fitZoom(cv, dpr);
  const tz = cam.follow ? fz * 2.6 : fz;
  const tx = cam.follow && ambVeh ? Math.max(60, Math.min(580, ambVeh.x + 22)) : 320, ty = 0;
  const k = cam.follow ? 0.08 : 0.12;
  cam.z += (tz - cam.z) * k; cam.x += (tx - cam.x) * k; cam.y += (ty - cam.y) * k;

  ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle='#0a101c'; ctx.fillRect(0,0,cv.width,cv.height);
  const z=cam.z*dpr, ox=cv.width/2-cam.x*z, oy=cv.height/2-cam.y*z;
  ctx.setTransform(z,0,0,z,ox,oy);
  ctx.drawImage(staticCanvas, WORLD.x0, WORLD.y0, WORLD.x1-WORLD.x0, WORLD.y1-WORLD.y0);

  // Corridor glow + mic rings
  snapshot.junctions.forEach((jn, j) => {
    const x = X[j];
    if (jn.mode==='SERVING' || jn.mode==='PREPARING') {
      const col = jn.mode==='SERVING'?'34,197,94':'245,158,11';
      const grad=ctx.createLinearGradient(x-90,0,x+12,0);
      grad.addColorStop(0,`rgba(${col},0)`); grad.addColorStop(1,`rgba(${col},.2)`);
      ctx.fillStyle=grad; ctx.fillRect(x-90,1.75,102,7);
      if (jn.mode==='SERVING') { ctx.fillStyle='rgba(34,197,94,.10)'; ctx.fillRect(x-BOX,-HALF,2*BOX,2*HALF); }
    }
    if (A && !A.done && A.s < x+BOX) {
      ctx.setLineDash([2,3]); ctx.lineWidth=0.35;
      ctx.strokeStyle=jn.acoustic.tier1?'rgba(245,158,11,.55)':'rgba(56,189,248,.18)';
      ctx.beginPath(); ctx.arc(x, 0, MIC*(0.92+0.04*Math.sin(t*3+j)), 0, 7); ctx.stroke(); ctx.setLineDash([]);
    }
  });

  // Route dashed line
  if (A && !A.done) {
    ctx.setLineDash([2.2,2.2]); ctx.strokeStyle='rgba(56,189,248,.75)'; ctx.lineWidth=0.55; ctx.lineDashOffset=-t*6;
    ctx.beginPath(); ctx.moveTo(A.x+4, 3.5); ctx.lineTo(ER_X, 3.5); ctx.stroke();
    ctx.setLineDash([]); ctx.lineDashOffset=0;
  }

  // Signals
  snapshot.junctions.forEach((jn, j) => {
    const x=X[j];
    bar(ctx,x-STOPOFF-0.1,1.75,0.55,7,jn.lights.W,dpr);
    bar(ctx,x+STOPOFF-0.45,-8.75,0.55,7,jn.lights.E,dpr);
    bar(ctx,x-5.25,-STOPOFF-0.45,3.5,0.55,jn.lights.N,dpr);
    bar(ctx,x+1.75,STOPOFF-0.1,3.5,0.55,jn.lights.S,dpr);
    lamp(ctx,x-STOPOFF-1.5,HALF+3.2,jn.lights.W,dpr);
    lamp(ctx,x+STOPOFF+1.5,-HALF-3.2,jn.lights.E,dpr);
    lamp(ctx,x-BOX-1.8,-STOPOFF-2.5,jn.lights.N,dpr);
    lamp(ctx,x+BOX+1.8,STOPOFF+2.5,jn.lights.S,dpr);
    ctx.strokeStyle=MODE_COL[jn.mode]; ctx.globalAlpha=jn.mode==='NORMAL'?0.25:0.9; ctx.lineWidth=0.7;
    ctx.shadowColor=MODE_COL[jn.mode]; ctx.shadowBlur=jn.mode==='NORMAL'?0:14*dpr;
    ctx.beginPath(); ctx.roundRect(x-BOX-1.2,-HALF-1.2,2*BOX+2.4,2*HALF+2.4,3); ctx.stroke();
    ctx.globalAlpha=1; ctx.shadowBlur=0;
  });

  // Vehicles (ambulance last)
  for (const v of snapshot.vehicles) {
    if (v.kind==='ambulance') continue;
    _drawVeh(ctx, v, t, dpr);
  }
  // Ambulance pulse rings
  if (ambVeh && A && !A.done) {
    for (let i=0; i<3; i++) {
      const ph=((t*0.9+i/3)%1);
      ctx.strokeStyle=`rgba(239,68,68,${0.5*(1-ph)})`; ctx.lineWidth=0.6;
      ctx.beginPath(); ctx.arc(ambVeh.x, ambVeh.y, 4+ph*26, 0, 7); ctx.stroke();
    }
    _drawVeh(ctx, ambVeh, t, dpr);
  }
  if (ambVeh && A?.done) {
    ctx.fillStyle='#22c55e'; ctx.font='800 7px system-ui'; ctx.textAlign='center'; ctx.fillText('ARRIVED ✓', ER_X, 0);
  }

  // Screen-space labels
  ctx.setTransform(1,0,0,1,0,0); ctx.textAlign='center';
  const sx = (x: number) => ox+x*z, sy = (y: number) => oy+y*z;
  snapshot.junctions.forEach((jn, j) => {
    const px=sx(X[j]), py=sy(-HALF-24), fs=12*dpr;
    ctx.font=`700 ${fs}px Inter,system-ui,sans-serif`;
    const label=`J${j+1}`, tw=ctx.measureText(label).width+62*dpr;
    ctx.fillStyle='rgba(10,16,28,.88)'; ctx.beginPath(); ctx.roundRect(px-tw/2,py-fs*1.15,tw,fs*1.75,8*dpr); ctx.fill();
    ctx.strokeStyle=MODE_COL[jn.mode]; ctx.lineWidth=1.2*dpr; ctx.stroke();
    ctx.fillStyle='#e6edf7'; ctx.textAlign='left'; ctx.fillText(label,px-tw/2+9*dpr,py+fs*0.2);
    ctx.fillStyle=MODE_COL[jn.mode]; ctx.font=`700 ${9.5*dpr}px Inter,system-ui,sans-serif`;
    ctx.fillText(jn.mode, px-tw/2+9*dpr+ctx.measureText(label).width*1.5+4*dpr, py+fs*0.18);
    ctx.textAlign='center';
  });
  const hp=sx(ER_X);
  ctx.fillStyle='#ef4444'; ctx.font=`800 ${11*dpr}px Inter,system-ui,sans-serif`; ctx.fillText('HOSPITAL ER',hp,sy(-HALF-24));
}

function _drawVeh(ctx: CanvasRenderingContext2D, v: { x:number;y:number;angle:number;len:number;speed:number;kind:string;braking:boolean }, t: number, dpr: number) {
  const hd = v.angle * Math.PI / 180;
  ctx.save(); ctx.translate(v.x, v.y); ctx.rotate(hd);
  const w = v.kind==='bus'?2.5:v.kind==='ambulance'?2.1:1.9;
  const L=v.len*1.18, W=w*1.3, braking=v.braking;
  if (v.kind==='ambulance') {
    const f=Math.floor(t*6)%2;
    ctx.fillStyle='rgba(239,68,68,.16)'; ctx.beginPath(); ctx.arc(0,0,13+2*Math.sin(t*6),0,7); ctx.fill();
    ctx.fillStyle='rgba(0,0,0,.4)'; ctx.beginPath(); ctx.roundRect(-L/2+.5,-W/2+.6,L,W,1.1); ctx.fill();
    ctx.fillStyle='#f8fafc'; ctx.beginPath(); ctx.roundRect(-L/2,-W/2,L,W,1.1); ctx.fill();
    ctx.fillStyle='#ef4444'; ctx.fillRect(-L/2+0.4,-W*0.12,L-0.8,W*0.24);
    ctx.fillStyle='#7dd3fc'; ctx.fillRect(L*0.2,-W/2+.5,L*0.18,W-1);
    ctx.fillStyle='#ef4444'; ctx.fillRect(-L*0.08,-0.35,1.8,0.7); ctx.fillRect(-L*0.08+0.55,-1.0,0.7,2);
    ctx.shadowBlur=16*dpr;
    ctx.fillStyle=f?'#ef4444':'#60a5fa'; ctx.shadowColor=ctx.fillStyle; ctx.fillRect(L*0.02,-W/2+.1,1,W/2-.2);
    ctx.fillStyle=f?'#60a5fa':'#ef4444'; ctx.shadowColor=ctx.fillStyle; ctx.fillRect(L*0.02,.1,1,W/2-.2);
    ctx.shadowBlur=0;
  } else {
    const col = (v as any).col ?? '#7dd3fc';
    ctx.fillStyle='rgba(0,0,0,.4)'; ctx.beginPath(); ctx.roundRect(-L/2+.5,-W/2+.6,L,W,1); ctx.fill();
    ctx.fillStyle=col; ctx.beginPath(); ctx.roundRect(-L/2,-W/2,L,W,v.kind==='bus'?.8:1.2); ctx.fill();
    ctx.fillStyle='rgba(8,14,28,.72)';
    if (v.kind==='bus') { for (let i=-3;i<=2;i++) ctx.fillRect(i*L/8.2,-W/2+.35,L/10,W-.7); }
    else { ctx.fillRect(L*0.08,-W/2+.35,L*.22,W-.7); ctx.fillRect(-L*.3,-W/2+.35,L*.14,W-.7); }
  }
  ctx.fillStyle='#fff6c9'; ctx.fillRect(L/2-.5,-W/2+.2,.5,.5); ctx.fillRect(L/2-.5,W/2-.7,.5,.5);
  ctx.fillStyle=braking?'#ff3b3b':'#6b1b1b';
  if (braking) { ctx.shadowColor='#ff3b3b'; ctx.shadowBlur=6*dpr; }
  ctx.fillRect(-L/2,-W/2+.2,.5,.6); ctx.fillRect(-L/2,W/2-.8,.5,.6); ctx.shadowBlur=0;
  ctx.restore();
}
