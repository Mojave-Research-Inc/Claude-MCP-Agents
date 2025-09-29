import fetch from 'cross-fetch';

const API = 'https://api.github.com';
function ghHeaders(etag?: string){
  const h: Record<string,string> = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'repo-harvester-mcp'
  };
  const tok = process.env.GITHUB_TOKEN;
  if (tok) h['Authorization'] = `Bearer ${tok}`;
  if (etag) h['If-None-Match'] = etag;
  return h;
}

export async function searchRepos(query: string, per_page=25){
  const url = `${API}/search/repositories?q=${encodeURIComponent(query)}&sort=stars&order=desc&per_page=${per_page}`;
  const res = await fetch(url, { headers: ghHeaders() });
  if (!res.ok) throw new Error(`GitHub search failed: ${res.status}`);
  const j = await res.json();
  return j.items as any[];
}

export async function getRepo(owner: string, name: string){
  const res = await fetch(`${API}/repos/${owner}/${name}`, { headers: ghHeaders() });
  if (!res.ok) throw new Error(`GitHub getRepo failed: ${res.status}`);
  return await res.json();
}

export async function getRepoLicense(owner: string, name: string){
  const res = await fetch(`${API}/repos/${owner}/${name}/license`, { headers: ghHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub license failed: ${res.status}`);
  const j = await res.json();
  return j.license?.spdx_id || j.license?.key || null;
}

export async function getRepoReadme(owner: string, name: string){
  const res = await fetch(`${API}/repos/${owner}/${name}/readme`, { headers: ghHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub readme failed: ${res.status}`);
  const j = await res.json();
  if (j && j.content && j.encoding === 'base64'){
    return Buffer.from(j.content, 'base64').toString('utf8');
  }
  return null;
}