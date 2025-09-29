import crypto from 'node:crypto';
export function sha256(buf: Buffer|string){
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(buf);
  return crypto.createHash('sha256').update(b).digest('hex');
}
export const sleep = (ms:number)=> new Promise(r=>setTimeout(r,ms));
export function now(){ return Date.now(); }