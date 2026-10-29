
import json

with open('freguesias_raw.json', encoding='utf-8') as fh:
    data = json.load(fh)

# organiza por codigo de municipio (primeiros 4 digitos do dtmnfr)
by_mun = {}
mun_names = {}
for f in data:
    dtmnfr = f['dtmnfr']
    mun_code = dtmnfr[:4]
    if mun_code not in by_mun:
        by_mun[mun_code] = []
    by_mun[mun_code].append([dtmnfr, f['freguesia'], f['municipio']])
    mun_names[mun_code] = f['municipio']

# ordena as freguesias dentro de cada municipio por nome
for code in by_mun:
    by_mun[code].sort(key=lambda x: x[1])

# gera o ficheiro JS
lines = ['/* Dados reais da DGT / CAOP2025 – gerado automaticamente */']
lines.append('const FREGUESIAS_LOCAL = {')
for mun_code in sorted(by_mun.keys()):
    frgs = by_mun[mun_code]
    entries = ', '.join('["' + f[0] + '","' + f[1] + '"]' for f in frgs)
    lines.append('  "' + mun_code + '": [' + entries + '],')
lines.append('};')
# nomes oficiais dos concelhos (codigo DICO de 4 digitos -> nome)
lines.append('const MUNICIPIOS_LOCAL = {')
for mun_code in sorted(mun_names):
    lines.append('  "' + mun_code + '": ' + json.dumps(mun_names[mun_code], ensure_ascii=False) + ',')
lines.append('};')

js_content = '\n'.join(lines)
with open('freguesias.js', 'w', encoding='utf-8') as fh:
    fh.write(js_content)

total_mun = len(by_mun)
total_frg = sum(len(v) for v in by_mun.values())
size_kb = len(js_content.encode('utf-8')) / 1024
print('Municipios:', total_mun)
print('Freguesias:', total_frg)
print('Tamanho: %.1f KB' % size_kb)

# mostra exemplo para Castelo Branco (0502)
print('Exemplo Castelo Branco (0502):')
for f in by_mun.get('0502', [])[:8]:
    print(' ', f[0], '->', f[1])
