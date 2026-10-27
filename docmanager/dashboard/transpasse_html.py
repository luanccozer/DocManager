"""Página HTML do Transpasse de Fase: a Planilha1 da equipe, desenhada a partir
do quadro montado em `core/transpasse.py`.

O modelo fica aqui dentro, como texto, e não num arquivo .html à parte: o
PyInstaller só leva para o executável os arquivos listados no `.spec`, e uma
página que faltasse no .exe só apareceria na máquina de quem usa. A página é
um arquivo único, sem nada da internet: abre com dois cliques em qualquer
navegador e pode ser enviada a quem não tem o DocManager.

Toda regra (pintura, dias, avisos) já vem calculada no JSON; o JavaScript só
desenha a grade e mostra o card ao passar o mouse.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from ..core.transpasse import MARCOS, Quadro

_MARCADOR = "/*__DADOS__*/"


def renderizar(quadro: Quadro, *, hoje: date, fontes: list[str], gerado_em: datetime) -> str:
    dados = {
        "hoje": hoje.isoformat(),
        "inicio": quadro.inicio.isoformat(),
        "fim": quadro.fim.isoformat(),
        "geradoEm": f"{gerado_em:%d/%m/%Y %H:%M}",
        "fontes": fontes,
        "grupos": [{
            "id": g.id, "sala": g.sala, "nome": g.nome, "pendente": g.pendente,
            "datas": {m: g.datas[m].isoformat() if g.datas[m] else None for m in MARCOS},
            "intervalos": g.intervalos, "dias": g.dias, "rodape": g.rodape, "avisos": g.avisos,
            "celulas": {dia.isoformat(): cor for dia, cor in sorted(g.celulas.items())},
        } for g in quadro.grupos],
    }
    # "</" dentro de um texto da planilha fecharia o <script> antes da hora.
    return MODELO.replace(_MARCADOR, json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transpasse de Fase</title>
<style>
:root { color-scheme: light; --R: #FF0000; --O: #FFC000; --B: #00B0F0; --G: #92D050; --K: #000000;
        --fds: #FFF2CC; --pendente: #FFFF00; }
body { margin: 0; padding: 18px 22px 40px; background: #fff; color: #000; font: 13px/1.35 Calibri, Aptos, "Segoe UI", sans-serif; }
h1 { font-size: 16px; margin: 0; }
.fonte { color: #595959; font-size: 11.5px; margin: 2px 0 12px; }
.legenda { display: inline-block; border: 1px solid #000; padding: 6px 12px 8px; margin-bottom: 14px; }
.legenda .item { display: flex; align-items: center; gap: 8px; padding: 1px 4px; border-radius: 3px; cursor: default; }
.legenda .item:hover { background: #f2f2f2; }
.legenda .sw { width: 24px; height: 12px; border: 1px solid #7f7f7f; flex: none; }
.legenda .dica { color: #595959; font-size: 11.5px; margin-top: 4px; }
.rolagem { overflow-x: auto; }
table { border-collapse: collapse; margin-bottom: 18px; }
th, td { padding: 0; }
th.cab { border: 2px solid #000; font-weight: 700; text-align: center; padding: 2px 6px; white-space: nowrap; }
th.dia { border: 1px solid #808080; border-bottom: 2px solid #000; font-weight: 400; font-size: 10.5px; min-width: 19px; width: 19px; height: 19px; text-align: center; }
th.dia.hoje { outline: 2px solid #000; outline-offset: -2px; font-weight: 700; }
th.titulo-dias { font-weight: 400; padding: 0 8px; vertical-align: bottom; cursor: help; }
td.sala { border: 1px solid #000; font-weight: 700; text-align: center; width: 26px; text-transform: uppercase; }
td.sala span { writing-mode: vertical-rl; transform: rotate(180deg); white-space: nowrap; }
td.geq { border: 1px solid #000; border-top-color: #bfbfbf; font-family: Aptos, Calibri, sans-serif; font-size: 12px; padding: 0 8px 0 5px; white-space: nowrap; height: 20px; }
td.geq.pendente { background: var(--pendente); }
td.c { border-left: 1px dotted #bfbfbf; border-bottom: 1px solid #e0e0e0; }
td.c.fds { background: var(--fds); }
td.c.hoje { border-right: 2px solid #000; }
td.R { background: var(--R) !important; } td.O { background: var(--O) !important; } td.B { background: var(--B) !important; }
td.G { background: var(--G) !important; } td.K { background: var(--K) !important; }
td.vao { width: 10px; }
td.dias { text-align: center; min-width: 40px; }
tr.grupo { cursor: default; }
tr.grupo:hover td.geq, tr.grupo:focus td.geq { background: #D9E1F2; font-weight: 700; }
tr.grupo:focus { outline: none; }
.foco td.c.pinta { opacity: .12; }
.foco-R td.c.R, .foco-O td.c.O, .foco-B td.c.B, .foco-G td.c.G, .foco-K td.c.K { opacity: 1; }
#tip { position: fixed; z-index: 10; pointer-events: none; background: #fff; border: 1px solid #7f7f7f; box-shadow: 0 4px 14px rgba(0,0,0,.18); padding: 8px 10px; font-size: 12.5px; max-width: 520px; }
#tip .t { font-weight: 700; }
#tip .s { color: #595959; margin-bottom: 5px; }
#tip table { margin: 0; }
#tip td { padding: 1px 10px 1px 0; white-space: nowrap; }
#tip td.n { color: #595959; text-align: right; }
#tip .sw { display: inline-block; width: 12px; height: 10px; border: 1px solid #7f7f7f; vertical-align: -1px; }
#tip .rodape { margin-top: 5px; font-weight: 700; }
#tip .aviso { margin-top: 3px; color: #595959; font-size: 11.5px; white-space: normal; }
</style>
</head>
<body>
<h1>ACOMPANHAMENTO DE TRANSPASSE DE FASES</h1>
<div class="fonte" id="fonte"></div>
<div class="legenda" id="legenda">
  <div>legenda das cores:</div>
  <div class="item" data-cor="R"><span class="sw" style="background:var(--R)"></span>Vermelho: data de convocação IB p/ inspeção conjunta</div>
  <div class="item" data-cor="O"><span class="sw" style="background:var(--O)"></span>Laranja: data da inspeção efetivamente realizada por IB</div>
  <div class="item" data-cor="B"><span class="sw" style="background:var(--B)"></span>Azul: data emissão CCMLC</div>
  <div class="item" data-cor="G"><span class="sw" style="background:var(--G)"></span>Verde: data do transpasse de fase (CCMLC emitido via UNIFIER)</div>
  <div class="item" data-cor="K"><span class="sw" style="background:var(--K)"></span>Preto: data do início efetivo da execução do comissionamento, quando time manutenção chega no local para execução</div>
  <div class="dica" id="dica"></div>
</div>
<div class="rolagem" id="grade"></div>
<div id="tip" hidden></div>
<script id="dados" type="application/json">/*__DADOS__*/</script>
<script>
'use strict';
const DADOS = JSON.parse(document.getElementById('dados').textContent);
const DIA = 864e5;
const toD = s => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d); };
const iso = t => new Date(t).toISOString().slice(0, 10);
const HOJE = toD(DADOS.hoje);
const fimDeSemana = t => { const w = new Date(t).getUTCDay(); return w === 0 || w === 6; };
const dd = s => s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '—';
const plural = n => `${n} dia${n === 1 ? '' : 's'}`;
const MESES = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO'];
const MARCOS = [['conv', 'R', 'Convocação'], ['insp', 'O', 'Inspeção IB'], ['ccmlc', 'B', 'Emissão CCMLC'],
                ['transp', 'G', 'Transpasse de fase'], ['inicio', 'K', 'Início do comissionamento']];

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else e.setAttribute(k, v);
  }
  for (const f of filhos) if (f != null) e.append(f);
  return e;
}

const DIAS = [];
for (let t = toD(DADOS.inicio); t <= toD(DADOS.fim); t += DIA) DIAS.push(t);
const meses = [];
for (const t of DIAS) {
  const m = new Date(t).getUTCMonth();
  if (!meses.length || meses.at(-1).m !== m) meses.push({ m, n: 0 });
  meses.at(-1).n++;
}

const grade = document.getElementById('grade');
document.getElementById('fonte').textContent = `Atualizado em ${DADOS.geradoEm} a partir de: ${DADOS.fontes.join(' e ')}`
  + (DADOS.fontes.length < 2 ? ' (sem a planilha complementar: o início do comissionamento e a coluna Dias ficam vazios)' : '');
document.getElementById('dica').textContent = `Passe o mouse sobre um grupo para ver as datas e os dias entre elas. `
  + `A linha preta vertical marca hoje (${dd(DADOS.hoje)}). Dias: da convocação ao início do comissionamento, contando os dois dias.`;
for (const item of document.querySelectorAll('#legenda .item')) {
  item.addEventListener('pointerenter', () => grade.classList.add('foco', `foco-${item.dataset.cor}`));
  item.addEventListener('pointerleave', () => grade.classList.remove('foco', `foco-${item.dataset.cor}`));
}

const tip = document.getElementById('tip');
function card(g) {
  const linhas = el('table');
  for (const [marco, cor, nome] of MARCOS) {
    const n = g.intervalos[marco];
    linhas.append(el('tr', {}, el('td', {}, el('span', { class: 'sw', style: `background:var(--${cor})` })),
      el('td', { text: nome }), el('td', { text: dd(g.datas[marco]) }), el('td', { class: 'n', text: n == null ? '' : plural(n) })));
  }
  return [el('div', { class: 't', text: g.nome ? `${g.id} · ${g.nome}` : g.id }), el('div', { class: 's', text: g.sala }),
    linhas, el('div', { class: 'rodape', text: g.rodape }), ...g.avisos.map(a => el('div', { class: 'aviso', text: `⚠ ${a}` }))];
}
function mostrar(ev, conteudo) { tip.replaceChildren(...conteudo); tip.hidden = false; mover(ev); }
function mover(ev) {
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 16, y = ev.clientY + 14;
  if (x + w > innerWidth - 8) x = ev.clientX - w - 16;
  if (y + h > innerHeight - 8) y = innerHeight - h - 8;
  tip.style.left = `${Math.max(8, x)}px`;
  tip.style.top = `${Math.max(8, y)}px`;
}

for (const sala of [...new Set(DADOS.grupos.map(g => g.sala))]) {
  const grupos = DADOS.grupos.filter(g => g.sala === sala);
  const cab1 = el('tr', {}, el('th', { rowspan: 2 }), el('th', { class: 'cab', rowspan: 2 }, 'GRUPO', el('br'), 'EQUIP.'));
  for (const m of meses) cab1.append(el('th', { class: 'cab', colspan: m.n, text: MESES[m.m] }));
  cab1.append(el('th', { rowspan: 2 }), el('th', { class: 'titulo-dias', rowspan: 2, text: 'Dias',
    title: 'Dias da convocação ao início do comissionamento, contando os dois dias' }));
  const cab2 = el('tr');
  for (const t of DIAS) cab2.append(el('th', { class: 'dia' + (t === HOJE ? ' hoje' : ''), title: t === HOJE ? 'hoje' : null,
    style: fimDeSemana(t) ? 'background:var(--fds)' : null, text: new Date(t).getUTCDate() }));
  const corpo = el('tbody');
  grupos.forEach((g, i) => {
    const tr = el('tr', { class: 'grupo', tabindex: 0 });
    if (i === 0) tr.append(el('td', { class: 'sala', rowspan: grupos.length }, el('span', { text: sala })));
    tr.append(el('td', { class: 'geq' + (g.pendente ? ' pendente' : ''), text: g.id }));
    for (const t of DIAS) {
      const cor = g.celulas[iso(t)];
      tr.append(el('td', { class: 'c' + (fimDeSemana(t) ? ' fds' : '') + (t === HOJE ? ' hoje' : '') + (cor ? ` pinta ${cor}` : '') }));
    }
    tr.append(el('td', { class: 'vao' }), el('td', { class: 'dias', text: g.dias ?? '' }));
    tr.addEventListener('pointerenter', ev => mostrar(ev, card(g)));
    tr.addEventListener('pointermove', mover);
    tr.addEventListener('pointerleave', () => { tip.hidden = true; });
    tr.addEventListener('focus', () => { const r = tr.getBoundingClientRect(); mostrar({ clientX: r.left + 140, clientY: r.bottom }, card(g)); });
    tr.addEventListener('blur', () => { tip.hidden = true; });
    corpo.append(tr);
  });
  grade.append(el('table', {}, el('thead', {}, cab1, cab2), corpo));
}
</script>
</body>
</html>
"""
