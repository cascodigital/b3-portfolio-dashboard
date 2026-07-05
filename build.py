#!/usr/bin/env python3
"""Painel de ações — build + push opcional pro Home Assistant.

Lê a watchlist (data/acoes.txt), as posições (data/carteira.json) e,
se existir, um radar de análise (data/radar.json ou RADAR_HTML_FILE),
busca cotações no Yahoo Finance, gera o HTML a partir de template.html
e opcionalmente publica via SSH.

Só usa a biblioteca padrão do Python — zero pip install.

Uso: python3 build.py [--no-push]

Variáveis de ambiente (todas opcionais):
  PAINEL_DATA_DIR   diretório com acoes.txt/carteira.json (default: ./data)
  RADAR_HTML_FILE   HTML de análise diária pra parsear (default: nenhum)
  PAINEL_SSH_DEST   destino do push, ex: root@homeassistant
  PAINEL_SSH_PORT   porta SSH (default: 22)
  PAINEL_SSH_PATH   path remoto (default: /config/www/painel-acoes.html)
"""
import json, os, re, subprocess, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('PAINEL_DATA_DIR', f'{BASE}/data')
TZ = ZoneInfo('America/Sao_Paulo')

SETOR = {
    'LREN3': 'Varejo', 'BBAS3': 'Bancos', 'ASAI3': 'Varejo', 'EGIE3': 'Utilities',
    'EQTL3': 'Utilities', 'HAPV3': 'Saúde', 'RDOR3': 'Saúde', 'BBSE3': 'Seguros',
    'PSSA3': 'Seguros', 'CYRE3': 'Construção', 'MRVE3': 'Construção',
    'RAIL3': 'Logística', 'RENT3': 'Locação', 'TOTS3': 'Tech', 'MULT3': 'Shoppings',
    'SBSP3': 'Saneamento', 'POMO4': 'Industrial', 'VIVT3': 'Telecom',
    'YDUQ3': 'Educação', 'ITUB4': 'Bancos', 'ABEV3': 'Consumo',
    'WEGE3': 'Industrial', 'B3SA3': 'Financeiro',
}

RADAR_DEFAULT = {
    'generatedAt': datetime.now(TZ).strftime('%Y-%m-%dT%H:%M'),
    'items': [
        {'t': '', 'kind': 'info', 'title': 'Radar não configurado',
         'body': 'Aponte RADAR_HTML_FILE pra uma análise diária ou edite data/radar.json.'},
    ],
}


def strip_tags(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s)).strip()


def parse_radar(html, gen_dt):
    """Extrai itens de um HTML de análise diária (template estrito — adapte ao seu)."""
    items = []
    m = re.search(r'<div style="background:#fff3cd[^"]*"><b>(.*?)</b>(.*?)</div>', html, re.S)
    if m:
        items.append({'t': 'BOVA11', 'kind': 'warn', 'title': strip_tags(m.group(1)).title(),
                      'body': strip_tags(m.group(2)).lstrip('— ')[:260]})
    blocks = re.split(r'(?=<h2 style="font-size:17px)', html)
    for b in blocks[1:]:
        h = re.match(r'<h2[^>]*>(\d)º — ([A-Z0-9]+) \| (R\$[\d.,]+) \| ([^|<]+) \|', b)
        if not h:
            continue
        rank, tick, preco, nome = h.group(1), h.group(2), h.group(3), h.group(4).strip()
        bm = re.search(r'text-transform:uppercase;background:[^"]*">([^<]+)</span>', b)
        badge = bm.group(1).strip() if bm else '?'
        kind = 'buy' if 'COMPRA' in badge else ('info' if 'OBSERVAR' in badge else 'warn')
        if kind == 'buy':
            oco = re.search(r'Alvo Conservador:\s*([+\-][\d,]+%)[^\n]*\n.*?Stop Loss:\s*(-[\d,]+%)', b, re.S)
            body = f'{preco} · Alvo {oco.group(1)} · Stop {oco.group(2)}' if oco else preco
        else:
            g = re.search(r'GATILHO p/ reativar:\s*(.*?)</div>', b, re.S)
            body = f'{preco} · Gatilho: {strip_tags(g.group(1))[:200]}' if g else f'{preco} · {nome}'
        items.append({'t': tick, 'kind': kind, 'title': f'{rank}º — {badge}', 'body': body})
    v = re.search(r'Lado Vendido.*?<div style="background:#fbeaea[^"]*">(.*?)</div>', html, re.S)
    if v:
        txt = strip_tags(v.group(1))
        if txt.startswith('Sem short'):
            items.append({'t': '', 'kind': 'info', 'title': 'Lado vendido',
                          'body': 'Sem short válido na lista hoje.'})
        else:
            for line in re.findall(r'<b>([A-Z0-9]+)</b>([^<]+)', v.group(1)):
                items.append({'t': line[0], 'kind': 'warn', 'title': 'short',
                              'body': strip_tags(line[1]).lstrip('— ')[:200]})
    if not items:
        raise ValueError('parser não achou itens')
    return {'generatedAt': gen_dt.strftime('%Y-%m-%dT%H:%M'), 'items': items}


def get_radar():
    cache = f'{DATA}/radar.json'
    src = os.environ.get('RADAR_HTML_FILE')
    if src and os.path.exists(src):
        try:
            radar = parse_radar(open(src).read(),
                                datetime.fromtimestamp(os.path.getmtime(src), TZ))
            json.dump(radar, open(cache, 'w'), ensure_ascii=False)
            return radar
        except Exception as ex:
            print(f'radar: usando cache/default ({ex})', file=sys.stderr)
    if os.path.exists(cache):
        return json.load(open(cache))
    return RADAR_DEFAULT


def get_agenda(now):
    from datetime import date, timedelta
    dsem = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM']
    today = now.date()
    evs = []
    for e in json.load(open(f'{BASE}/events.json'))['eventos']:
        d = date.fromisoformat(e['data'])
        if d >= today:
            evs.append((d, e['titulo'], e['info']))
    d, focus_done = today, False
    for _ in range(40):  # próximo Focus (segunda) e payrolls (1ª sexta do mês)
        d += timedelta(days=1)
        if d.weekday() == 0 and not focus_done:
            evs.append((d, 'Boletim Focus', 'expectativas Selic/IPCA · 08:25'))
            focus_done = True
        if d.weekday() == 4 and d.day <= 7:
            evs.append((d, 'Payroll EUA', 'alto impacto · 09:30'))
    evs.sort()
    out = ''
    for d, tit, info in evs[:5]:
        out += (f'<div class="ag"><span class="d">{dsem[d.weekday()]} {d:%d/%m}</span>'
                f'<div class="e">{tit}</div><span class="i">{info}</span></div>\n')
    return out


def fetch(sym, rng='3mo'):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?range={rng}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    d = json.load(urllib.request.urlopen(req, timeout=20))['chart']['result'][0]
    closes = [round(c, 2) for c in d['indicators']['quote'][0]['close'] if c]
    return d['meta']['regularMarketPrice'], closes


def main():
    cart = json.load(open(f'{DATA}/carteira.json'))
    owned = {p['ticker']: {'q': p['qtd'], 'e': p['preco_entrada']} for p in cart['posicoes']}

    tickers = [l.strip().replace('.SA', '') for l in open(f'{DATA}/acoes.txt') if l.strip()]
    for t in owned:
        if t not in tickers:
            tickers.append(t)

    D, fails = {}, []
    for t in tickers:
        try:
            p, h = fetch(t + '.SA')
            if len(h) < 3:
                raise ValueError('histórico curto')
            D[t] = {'p': round(p, 2), 'pd': h[-2], 's': SETOR.get(t, 'B3'), 'h': h[-30:]}
        except Exception as ex:
            fails.append(f'{t}: {ex}')
    if len(D) < max(3, len(tickers) // 2):
        sys.exit(f'ABORTADO: só {len(D)}/{len(tickers)} cotações OK. Falhas: {fails}')

    missing = [t for t in owned if t not in D]
    if missing:
        sys.exit(f'ABORTADO: posição sem cotação: {missing}')

    IDX = {}
    for key, sym in (('IBOV', '^BVSP'), ('USDBRL', 'BRL=X')):
        p, h = fetch(sym)
        IDX[key] = {'p': round(p, 4 if key == 'USDBRL' else 0), 'pd': h[-2], 'h': h[-30:]}

    radar = get_radar()

    now = datetime.now(TZ)
    dias = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM']
    built = f'atualizado {dias[now.weekday()]} {now:%H:%M}'

    html = open(f'{BASE}/template.html').read()
    html = html.replace('/*__DATA__*/', 'const D=' + json.dumps(D, ensure_ascii=False)
                        + ';\nconst IDX=' + json.dumps(IDX) + ';\n')
    html = html.replace('/*__OWNED__*/', 'const OWNED=' + json.dumps(owned, ensure_ascii=False) + ';')
    html = html.replace('/*__RADAR__*/', 'const RADAR=' + json.dumps(radar, ensure_ascii=False) + ';')
    html = html.replace('<!--__AGENDA__-->', get_agenda(now))
    html = html.replace('__BUILT__', built)

    out = f'{BASE}/painel-acoes.html'
    open(out, 'w').write(html)

    dest = os.environ.get('PAINEL_SSH_DEST')
    if '--no-push' not in sys.argv and dest:
        port = os.environ.get('PAINEL_SSH_PORT', '22')
        rpath = os.environ.get('PAINEL_SSH_PATH', '/config/www/painel-acoes.html')
        r = subprocess.run(
            ['ssh', '-p', port, '-o', 'StrictHostKeyChecking=no',
             '-o', 'ConnectTimeout=10', dest, f'cat > {rpath}'],
            stdin=open(out), capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f'push falhou: {r.stderr[:300]}')

    print(f'OK {built} | {len(D)} tickers | falhas: {fails or "nenhuma"}')


if __name__ == '__main__':
    main()
