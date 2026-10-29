#!/usr/bin/env python3
"""
Servidor local da app "Os meus terrenos".
 - serve esta pasta (index.html, ...)
 - faz de ponte para o SNIC (sem bloqueios CORS) e GUARDA cada resposta em dados/cache/,
   por isso a segunda vez que pedires a mesma secção/prédio a resposta é instantânea e local.

Uso (na pasta do projeto):   python servidor.py        e abre   http://localhost:8000
Outra porta:                 python servidor.py 8080
"""
import hashlib, http.server, json, os, socketserver, sys, urllib.error, urllib.request

UPSTREAM = os.environ.get('SNIC_UPSTREAM', 'https://snic.dgterritorio.gov.pt/geoportal/dgt_snic2/api/app/search/cgpr')
UPSTREAM_WS = os.environ.get('WS_UPSTREAM', 'https://snicws.dgterritorio.gov.pt/geoserver/inspire/ows')   # WMS/GetFeatureInfo (rota /snicws)
UPSTREAM_OGC = os.environ.get('OGC_UPSTREAM', 'https://ogcapi.dgterritorio.gov.pt')   # OGC API da DGT (rota /ogc/)
UPSTREAM_PREDIO = os.environ.get('SNIC_UPSTREAM_PREDIO', 'https://snic.dgterritorio.gov.pt/geoportal/dgt_snic2/api/app/search/predio')
CACHE = os.path.join('dados', 'cache')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
           'Referer': 'https://snic.dgterritorio.gov.pt/visualizadorCadastro'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/snic/'):
            return self.ponte(UPSTREAM, self.path[len('/snic/'):])
        if self.path.startswith('/snicws'):          # WMS GetFeatureInfo da DGT
            return self.ponte(UPSTREAM_WS, self.path[len('/snicws'):].lstrip('/'))
        if self.path.startswith('/ogc/'):            # OGC API da DGT (sem bloqueios CORS)
            return self.ponte(UPSTREAM_OGC, self.path[len('/ogc/'):])
        if self.path.startswith('/snicp/'):          # geometria do prédio
            return self.ponte(UPSTREAM_PREDIO, self.path[len('/snicp/'):])
        super().do_GET()

    def ponte(self, upstream, resto):
        os.makedirs(CACHE, exist_ok=True)
        ficheiro = os.path.join(CACHE, hashlib.sha1((upstream + resto).encode()).hexdigest() + '.json')
        alvo = upstream + (resto if resto.startswith('?') else '/' + resto)
        da_cache = os.path.exists(ficheiro)
        if da_cache:
            corpo, estado = open(ficheiro, 'rb').read(), 200
        else:
            try:
                with urllib.request.urlopen(urllib.request.Request(alvo, headers=HEADERS), timeout=40) as r:
                    corpo, estado = r.read(), r.status
                if estado == 200 and corpo.strip():
                    open(ficheiro, 'wb').write(corpo)
            except urllib.error.HTTPError as e:
                corpo, estado = e.read() or b'', e.code
            except Exception as e:
                corpo, estado = json.dumps({'erro': str(e)}).encode(), 502
        sys.stderr.write(f'SNIC {estado}{" (cache)" if da_cache else ""}  {alvo}\n')
        self.send_response(estado)
        self.send_header('X-Servidor-Local', '1')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, fmt, *args):
        pass   # o registo dos pedidos ao SNIC é feito em ponte()


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    print(f'App em  http://localhost:{PORT}   (Ctrl+C para parar)')
    Servidor(('', PORT), Handler).serve_forever()
