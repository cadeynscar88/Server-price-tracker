// Minimal service worker: cache app shell, network-first for tracker pages/data.
const SHELL = "pst-shell-v8";
const SHELL_FILES = ["./", "./index.html", "./history.html", "./manifest.webmanifest"];
self.addEventListener("install", e => {e.waitUntil(caches.open(SHELL).then(c=>c.addAll(SHELL_FILES)).then(()=>self.skipWaiting()));});
self.addEventListener("activate", e => {e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==SHELL).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch", e => {
 const url=new URL(e.request.url); if(e.request.method!=="GET")return;
 if(url.pathname.includes("/data/")||url.hostname.includes("api.")||url.hostname.includes("github")){
  e.respondWith(fetch(e.request,{cache:"no-store"}).then(res=>{const copy=res.clone();caches.open(SHELL).then(c=>c.put(e.request,copy));return res;}).catch(()=>caches.match(e.request)));return;
 }
 if(e.request.mode==="navigate"&&(url.pathname.endsWith("/")||url.pathname.endsWith("/index.html")||url.pathname.endsWith("/history.html"))){
  e.respondWith(fetch(e.request,{cache:"no-store"}).then(res=>{const copy=res.clone();caches.open(SHELL).then(c=>c.put(e.request,copy));return res;}).catch(()=>url.pathname.endsWith("/history.html")?caches.match("./history.html"):caches.match("./index.html")));return;
 }
 e.respondWith(caches.match(e.request).then(hit=>hit||fetch(e.request)));
});
