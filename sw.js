// Minimal service worker: cache app shell, network-first for tracker data.
const SHELL = "pst-shell-v7";
const SHELL_FILES = ["./", "./index.html", "./history.html", "./history-hook.js", "./manifest.webmanifest"];
self.addEventListener("install", e => {e.waitUntil(caches.open(SHELL).then(c=>c.addAll(SHELL_FILES)).then(()=>self.skipWaiting()));});
self.addEventListener("activate", e => {e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==SHELL).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch", e => {
 const url=new URL(e.request.url); if(e.request.method!=="GET")return;
 if(url.pathname.includes("/data/")||url.hostname.includes("api.")||url.hostname.includes("github")){
  e.respondWith(fetch(e.request).then(res=>{const copy=res.clone();caches.open(SHELL).then(c=>c.put(e.request,copy));return res;}).catch(()=>caches.match(e.request)));return;
 }
 if(e.request.mode==="navigate"&&(url.pathname.endsWith("/")||url.pathname.endsWith("/index.html"))){
  e.respondWith(fetch(e.request).then(async res=>{let html=await res.text();if(!html.includes("history-hook.js"))html=html.replace("</body>","<script src=\"history-hook.js?v=2\"></script></body>");return new Response(html,{status:res.status,statusText:res.statusText,headers:{"content-type":"text/html; charset=utf-8"}})}).catch(()=>caches.match("./index.html")));return;
 }
 if(e.request.mode==="navigate"&&url.pathname.endsWith("/history.html")){
  e.respondWith(fetch(e.request,{cache:"no-store"}).catch(()=>caches.match("./history.html")));return;
 }
 e.respondWith(caches.match(e.request).then(hit=>hit||fetch(e.request)));
});
