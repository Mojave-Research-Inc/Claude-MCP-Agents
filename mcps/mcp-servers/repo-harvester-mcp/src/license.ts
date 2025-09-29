import correct from 'spdx-correct';
// @ts-ignore - spdx-license-ids doesn't have proper type declarations
import { licenses as SPDX_IDS } from 'spdx-license-ids';

export function normalizeLicense(id?: string|null){
  if (!id) return null;
  const c = correct(id);
  if (c) return c;
  // crude fallback for common variants
  if (/apache/i.test(id)) return 'Apache-2.0';
  if (/mit/i.test(id)) return 'MIT';
  if (/bsd/i.test(id) && /3/i.test(id)) return 'BSD-3-Clause';
  if (/bsd/i.test(id) && /2/i.test(id)) return 'BSD-2-Clause';
  if (/mpl/i.test(id)) return 'MPL-2.0';
  if (/gpl/i.test(id)) return 'GPL-3.0';
  return id;
}

export function licenseAllowed(source: string|null, allow: string[], deny: string[]): { allowed: boolean; reason: string }{
  if (!source) return { allowed: false, reason: 'Unknown license' };
  const norm = normalizeLicense(source);
  if (!norm) return { allowed: false, reason: 'Unrecognized license' };
  if (deny.includes(norm)) return { allowed: false, reason: `Denied by policy: ${norm}` };
  if (allow.includes(norm)) return { allowed: true, reason: `Allowed: ${norm}` };
  return { allowed: false, reason: `Not in allow-list: ${norm}` };
}