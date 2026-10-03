import { spawn } from 'node:child_process';
import { mkdtemp, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'vite';

const candidates = [process.env.FOLIONYM_BROWSER, '/Applications/Chromium.app/Contents/MacOS/Chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium', '/usr/bin/google-chrome'].filter(Boolean);
let executable;
for (const candidate of candidates) { try { await access(candidate); executable = candidate; break; } catch { /* Check next installed browser. */ } }
if (!executable) throw Error('Set FOLIONYM_BROWSER to an installed Chromium executable. No browser is downloaded.');
const server = await createServer({
  server:{host:'127.0.0.1',port:0,strictPort:false},
  plugins:[{name:'smoke-thumbnails',configureServer(server){server.middlewares.use((request,response,next)=>{
    if (request.url?.endsWith('/thumbnail')) {response.setHeader('Content-Type','image/svg+xml');response.end('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>');}
    else next();
  });}}],
});
await server.listen();
const profile = await mkdtemp(join(tmpdir(),'folionym-smoke-'));
const address = server.httpServer.address();
try {
  await new Promise((resolve,reject)=>{
    const child = spawn(executable,['--headless','--disable-gpu','--no-first-run',`--user-data-dir=${profile}`,'--virtual-time-budget=15000','--dump-dom',`http://127.0.0.1:${address.port}/tests/smoke.html`],{stdio:['ignore','pipe','pipe']});
    let output=''; let errors='';
    const deadline=setTimeout(()=>{child.kill();reject(Error(`Browser smoke timed out. ${output} ${errors}`));},30000);
    child.stdout.on('data',data=>{output+=data;if(output.includes('data-result="passed"')){clearTimeout(deadline);child.kill();console.log(output.match(/<div id="results">([\s\S]*?)<\/div>/)?.[1] ?? 'Browser smoke passed');resolve();}});
    child.stderr.on('data',data=>{errors+=data;});
    child.on('error',error=>{clearTimeout(deadline);reject(error);});
    child.on('exit',()=>{clearTimeout(deadline);if(!output.includes('data-result="passed"')) reject(Error(`Browser smoke failed: ${output} ${errors}`));});
  });
} finally { await server.close(); await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200}); }
