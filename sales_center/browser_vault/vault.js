'use strict';
// This component has no third-party scripts or network requests.
const encoder = new TextEncoder();
const decoder = new TextDecoder();
const DB_NAME = 'sales-center-private-vault-v1';
const STORE = 'connections';
let lastRequest = '';
let queue = Promise.resolve();
function send(value) {
  window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',dataType:'json',value}, window.location.origin);
}
function database() {
  return new Promise((resolve,reject) => {
    const request = indexedDB.open(DB_NAME,1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('storage'));
  });
}
async function record(owner) {
  const db = await database();
  try {
    return await new Promise((resolve,reject) => {
      const request=db.transaction(STORE,'readonly').objectStore(STORE).get(owner);
      request.onsuccess=()=>resolve(request.result);
      request.onerror=()=>reject(new Error('storage'));
    });
  } finally { db.close(); }
}
async function write(owner,value,remove=false) {
  const db=await database();
  try {
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,'readwrite');
      if (remove) tx.objectStore(STORE).delete(owner);
      else tx.objectStore(STORE).put(value,owner);
      tx.oncomplete=()=>resolve();
      tx.onerror=()=>reject(new Error('storage'));
      tx.onabort=()=>reject(new Error('storage'));
    });
  } finally {db.close();}
}
async function transportSnapshot(text) {
  if (typeof text!=='string' || text.length<1024*1024 || typeof CompressionStream==='undefined') return text;
  try {
    // Compress the signed STRING, never parse large numeric IDs in JavaScript.
    const stream=new Blob([text]).stream().pipeThrough(new CompressionStream('deflate'));
    const bytes=new Uint8Array(await new Response(stream).arrayBuffer());
    let binary='';
    for(let offset=0;offset<bytes.length;offset+=8192) binary+=String.fromCharCode(...bytes.subarray(offset,offset+8192));
    return JSON.stringify({transport:'zlib-base64',data:btoa(binary)});
  } catch (_) {return text;}
}
async function handle(args) {
  const base={request_id:args.request_id,owner:args.owner};
  try {
    if (args.operation==='idle') {send({...base,status:'idle'});return;}
    if (!window.isSecureContext || !crypto.subtle || !indexedDB) throw new Error('unavailable');
    if (args.operation==='forget') {
      await write(args.owner,null,true);
      send({...base,status:'forgotten'});
      return;
    }
    const previous=await record(args.owner);
    if (args.operation==='load') {
      if (!previous) {send({...base,status:'empty'});return;}
      if (previous.version!==1 || !previous.key || previous.key.extractable) throw new Error('invalid');
      const bytes=await crypto.subtle.decrypt({name:'AES-GCM',iv:previous.iv,additionalData:encoder.encode(DB_NAME+':'+args.owner)},previous.key,previous.cipher);
      const payload=JSON.parse(decoder.decode(bytes));
      if (typeof payload.token!=='string' || !payload.token || payload.owner!==args.owner) throw new Error('invalid');
      send({...base,status:'restored',token:payload.token,snapshot_json:await transportSnapshot(payload.snapshot_json||''),interval:payload.interval});
      return;
    }
    if (args.operation==='save') {
      if (typeof args.token!=='string' || !args.token) throw new Error('invalid');
      const key=previous && previous.version===1 && previous.key && !previous.key.extractable ? previous.key : await crypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);
      const iv=crypto.getRandomValues(new Uint8Array(12));
      // The snapshot remains a STRING: JSON numbers containing large IDs must never pass through JavaScript number conversion.
      const payload=JSON.stringify({owner:args.owner,token:args.token,snapshot_json:args.snapshot_json||'',interval:args.interval});
      const cipher=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:encoder.encode(DB_NAME+':'+args.owner)},key,encoder.encode(payload));
      await write(args.owner,{version:1,key,iv,cipher});
      send({...base,status:'saved'});
    }
  } catch (_) {
    // Do not expose exception bodies, tokens, ciphertext or customer data.
    send({...base,status:'error'});
  }
}
window.addEventListener('message',event=>{
  if (window.parent===window || event.source!==window.parent || event.origin!==window.location.origin || !event.data || event.data.type!=='streamlit:render') return;
  const args=event.data.args||{};
  if (!args.owner || !args.request_id || !['load','save','forget','idle'].includes(args.operation)) return;
  const request=args.owner+':'+args.request_id+':'+args.operation;
  if (lastRequest===request) return;
  lastRequest=request;
  queue=queue.then(()=>handle(args));
});
window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:componentReady',apiVersion:1},window.location.origin);
window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setFrameHeight',height:0},window.location.origin);
