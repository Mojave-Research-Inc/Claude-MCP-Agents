import yaml from 'js-yaml';
import fs from 'node:fs';

export type CopyleftMode = 'allow_weak'|'deny_all'|'project_is_gpl';
export interface Policies {
  license_allow: string[];
  license_deny: string[];
  copyleft_mode: CopyleftMode;
  providers: any;
  integration: { strategy: 'vendor'|'subtree'|'package'; target_repo_path: string; vendor_dir: string };
  quality_weights: { relevance:number; maintenance:number; tests:number; docs:number; popularity:number };
}

export function loadPolicies(path: string): Policies {
  const doc = yaml.load(fs.readFileSync(path,'utf8')) as any;
  return doc as Policies;
}