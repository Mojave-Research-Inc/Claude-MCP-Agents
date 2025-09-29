export interface SBOMComponent { name: string; version: string; license?: string; purl?: string; }
export interface SBOM { version: string; components: SBOMComponent[] }

export function sbomDelta(current: SBOM, add: SBOMComponent[]): SBOM {
  const existing = new Set(current.components.map(c=>`${c.name}@${c.version}`));
  const merged = [...current.components];
  for (const c of add){
    const key = `${c.name}@${c.version}`;
    if (!existing.has(key)) merged.push(c);
  }
  return { version: current.version, components: merged };
}