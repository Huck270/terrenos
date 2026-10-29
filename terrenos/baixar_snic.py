#!/usr/bin/env python3
"""
Descarrega do SNIC (DGT) as secções e os prédios de TODAS as freguesias que têm cadastro rústico
(CGPR) para ficheiros locais em dados/. A app lê esses ficheiros primeiro (listas instantâneas e offline).

Uso (na pasta do projeto, onde está o freguesias_raw.json):
    python baixar_snic.py                  todo o Continente (pode demorar; retoma de onde parou)
    python baixar_snic.py 0502 0105        só estes concelhos (4 dígitos) ou freguesias (6 dígitos)
    python baixar_snic.py --refazer        volta a descarregar tudo, mesmo o que já existe
    python baixar_snic.py --paralelo 10    mais pedidos em simultâneo (por omissão, 6)

Ctrl+C pára com segurança: ao voltar a correr, continua nas freguesias que faltam.
Cria:  dados/<freguesia>.json  e  dados/indice.json (freguesias com e sem cadastro).
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.environ.get('SNIC_UPSTREAM', 'https://snic.dgterritorio.gov.pt/geoportal/dgt_snic2/api/app/search/cgpr')
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
           'Referer': 'https://snic.dgterritorio.gov.pt/visualizadorCadastro'}
PARAMS_SECCAO = ['seccao', 'secao', 'sec']
param_ok = None


def get(caminho, params):
    url = f'{BASE}/{caminho}?{urllib.parse.urlencode(params)}'
    for t in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as r:
                texto = r.read().decode('utf-8', 'replace')
            try:
                return json.loads(texto)
            except ValueError:
                return texto
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
        except Exception:
            pass
        time.sleep(2 * (t + 1))
    raise RuntimeError('Sem resposta do SNIC: ' + url)


def lista_de(d):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        return next((v for v in d.values() if isinstance(v, list)), None)
    return None


def valor(item, dica):
    if not isinstance(item, dict):
        return '' if item is None else str(item).strip()
    k = next((k for k in item if re.search(dica, k, re.I)), None) or next((k for k in item if not isinstance(item[k], (dict, list))), None)
    return str(item[k]).strip() if k else ''


def natural(s):
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', s)]


def predios(freg, sec):
    global param_ok
    for nome in ([param_ok] if param_ok else PARAMS_SECCAO):
        try:
            d = get('predios', {'dicofre': freg, nome: sec})
        except urllib.error.HTTPError:
            continue
        arr = lista_de(d)
        if arr is None:
            continue
        itens = []
        for x in arr:
            if isinstance(x, dict):
                ks = next((k for k in x if re.search('seccao', k, re.I)), None)
                if ks and str(x[ks]).strip().upper() != sec:
                    continue
            itens.append(valor(x, r'^(predio|numero|nr?_?predio|artigo|num)'))
        itens = sorted({i for i in itens if i}, key=natural)
        if itens:
            param_ok = nome
            return itens
    return []


def seccoes(freg):
    """Lista de secções da freguesia; None se o pedido falhou (diferente de lista vazia = sem cadastro)."""
    try:
        arr = lista_de(get('seccoes', {'filter': freg}))
    except Exception:
        return None
    if arr is None:
        return []
    return sorted({valor(x, 'seccao').upper() for x in arr if valor(x, 'seccao')}, key=natural)


def escrever_indice(pasta, sem):
    com = sorted(f[:-5] for f in os.listdir(pasta) if re.fullmatch(r'\d{6}\.json', f))
    json.dump({'com': com, 'sem': sorted(set(sem) - set(com))}, open(os.path.join(pasta, 'indice.json'), 'w'), separators=(',', ':'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('codigos', nargs='*', help='concelho (4 dígitos) ou freguesia (6 dígitos); vazio = todo o Continente')
    ap.add_argument('--refazer', action='store_true')
    ap.add_argument('--paralelo', type=int, default=6)
    ap.add_argument('--saida', default='dados')
    a = ap.parse_args()

    raw = json.load(open('freguesias_raw.json', encoding='utf-8'))
    nomes = {f['dtmnfr']: f['freguesia'] for f in raw}
    if a.codigos:
        lista = []
        for c in a.codigos:
            lista += [d for d in nomes if d.startswith(c)] if len(c) == 4 else [c]
    else:
        lista = list(nomes)
    if not lista:
        sys.exit('Nenhuma freguesia encontrada para esses códigos.')
    os.makedirs(a.saida, exist_ok=True)
    ind = os.path.join(a.saida, 'indice.json')
    sem = set(json.load(open(ind)).get('sem', [])) if os.path.exists(ind) else set()

    pendentes = [f for f in lista if a.refazer or not (os.path.exists(os.path.join(a.saida, f'{f}.json')) or f in sem)]
    print(f'{len(lista)} freguesias no pedido, {len(pendentes)} por verificar.')
    t0 = time.time()
    try:
        # Fase 1: quais as freguesias com cadastro (em paralelo, 1 pedido cada)
        com, falhadas = {}, []
        with ThreadPoolExecutor(a.paralelo) as ex:
            for i, (f, s) in enumerate(zip(pendentes, ex.map(seccoes, pendentes)), 1):
                if s is None:
                    falhadas.append(f)
                elif s:
                    com[f] = s
                else:
                    sem.add(f)
                if i % 100 == 0 or i == len(pendentes):
                    print(f'  verificadas {i}/{len(pendentes)} freguesias: {len(com)} com cadastro, {len(sem)} sem', end='\r')
        print()
        escrever_indice(a.saida, sem)

        # Fase 2: prédios de cada secção (em paralelo dentro de cada freguesia)
        for n, (freg, secs) in enumerate(com.items(), 1):
            print(f'[{n}/{len(com)}] {freg} {nomes.get(freg, "")}', end=' ', flush=True)
            dados = {}
            for s in secs:                       # a 1.ª secção com prédios descobre o nome do parâmetro
                dados[s] = predios(freg, s)
                if param_ok:
                    break
            if not param_ok:
                sys.exit('\nNão consegui obter prédios. No SNIC (F12 > Rede) copia o endereço e a resposta do pedido "predios".')
            resto = [s for s in secs if s not in dados]
            with ThreadPoolExecutor(a.paralelo) as ex:
                for s, p in zip(resto, ex.map(lambda s: predios(freg, s), resto)):
                    dados[s] = p
            dados = {s: p for s, p in dados.items() if p}
            json.dump({'f': freg, 's': dados}, open(os.path.join(a.saida, f'{freg}.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
            print(f'- {len(dados)} secções, {sum(len(p) for p in dados.values())} prédios  [{int(time.time() - t0)}s]')
        if falhadas:
            print(f'\n{len(falhadas)} freguesias falharam por rede; volta a correr o comando para as repetir.')
    finally:
        escrever_indice(a.saida, sem)
    print('Concluído.')


if __name__ == '__main__':
    main()
