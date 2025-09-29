import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { generateNoticeBlock } from './notice.js';

export interface IntegrationSpec {
  target_repo: string; // local path
  strategy: 'vendor'|'subtree'|'package';
  selection: { path: string; dest: string; contents?: string }[]; // vendor: explicit files
  spdx?: { headers?: string[] };
  notice?: { add: string[] };
  sbom?: { components: { name:string; version:string; license?:string; purl?:string; sourceUrl?:string }[] };
  branch?: string;
}

export async function stage(spec: IntegrationSpec){
  // For vendor strategy, write files directly under target path
  const branch = spec.branch ?? `harvest/${Date.now()}`;
  // assume caller created branch; here we only write files
  for (const sel of spec.selection){
    const destPath = path.join(spec.target_repo, sel.dest);
    await fs.mkdir(path.dirname(destPath), { recursive: true });
    if (sel.contents !== undefined){
      await fs.writeFile(destPath, sel.contents, 'utf8');
    } else {
      // no-op; selection expects contents, or caller copies actual tree
      await fs.writeFile(destPath, '', 'utf8');
    }
  }
  // Update NOTICE
  if (spec.notice?.add?.length){
    const np = path.join(spec.target_repo, 'NOTICE');
    const existing = fssync.existsSync(np) ? await fs.readFile(np, 'utf8') : '';
    const block = generateNoticeBlock(spec.sbom?.components?.map(c=>({name:c.name, license:c.license, sourceUrl:c.sourceUrl})) ?? []);
    const merged = `${existing}\n\n${block}\n\n${spec.notice.add.join('\n')}`;
    await fs.writeFile(np, merged, 'utf8');
  }
  return { branch, wrote: spec.selection.map(s=>s.dest) };
}