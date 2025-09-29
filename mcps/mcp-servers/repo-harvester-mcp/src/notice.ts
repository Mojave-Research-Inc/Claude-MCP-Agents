export function generateNoticeBlock(components: {name:string; license?:string; sourceUrl?:string}[]): string{
  const lines: string[] = [];
  lines.push('THIRD-PARTY NOTICES');
  lines.push('');
  for (const c of components){
    lines.push(`- ${c.name}${c.license?` (${c.license})`:''}${c.sourceUrl?` — ${c.sourceUrl}`:''}`);
  }
  lines.push('');
  lines.push('This distribution includes third-party components licensed under their respective licenses.');
  return lines.join('\n');
}