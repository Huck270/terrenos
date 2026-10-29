/* Service Worker mínimo da app "Os meus terrenos".
   Serve para: (1) cumprir os requisitos de instalação no telemóvel; (2) abrir a app sem rede.
   Guarda a "casca" da app (index.html, freguesias.js, ícones, bibliotecas). NÃO guarda mapas, SNIC, DGT, WMS nem pesquisas.
   Ao alterar ficheiros da app, mude VERSAO (ex.: terrenos-v2) para forçar a atualização. */
const VERSAO = 'terrenos-v4';
const CASCA = ['./', 'index.html', 'manifest.json', 'freguesias.js',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-maskable-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSAO)
    .then(c => Promise.all(CASCA.map(u => c.add(u).catch(() => {}))))   // um ficheiro em falta não impede a instalação
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const guardar = (req, res) => caches.open(VERSAO).then(c => c.put(req, res));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // dados que mudam ou são enormes: vão sempre à rede, sem cache
  const dinamico = /^\/(snicp?|snicws|ogc)(\/|$)/.test(url.pathname) ||
    /dgterritorio\.gov\.pt|allorigins\.win|nominatim|openstreetmap\.org|arcgisonline\.com|arcgis\.com|cartocdn\.com|opentopomap\.org/.test(url.hostname);
  if (dinamico) return;

  const mesmoSitio = url.origin === self.location.origin;
  const biblioteca = /(^|\.)unpkg\.com$|^cdn\.tailwindcss\.com$|^cdnjs\.cloudflare\.com$|^fonts\.googleapis\.com$|^fonts\.gstatic\.com$/.test(url.hostname);
  if (!mesmoSitio && !biblioteca) return;

  if (req.mode === 'navigate') {   // página: rede primeiro; sem rede, usa a cópia guardada
    e.respondWith(fetch(req)
      .then(r => { guardar(req, r.clone()); return r; })
      .catch(() => caches.match(req).then(r => r || caches.match('index.html') || caches.match('./'))));
    return;
  }
  // restantes ficheiros: cache primeiro e atualiza em segundo plano
  e.respondWith(caches.match(req).then(guardado => {
    const rede = fetch(req).then(r => { if (r && (r.ok || r.type === 'opaque')) guardar(req, r.clone()); return r; }).catch(() => guardado);
    return guardado || rede;
  }));
});
