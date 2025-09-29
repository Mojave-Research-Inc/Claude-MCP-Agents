import { adjudicate } from "./adjudicator.js";
import http from "node:http";

if (!process.env.OPENAI_API_KEY) console.warn("WARN: OPENAI_API_KEY not set");
if (!process.env.XAI_API_KEY) console.warn("WARN: XAI_API_KEY not set");

const server = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/adjudicate"){
    const bufs: Buffer[] = [];
    for await (const c of req) bufs.push(c as Buffer);
    const body = JSON.parse(Buffer.concat(bufs).toString("utf8"));
    const { facts, budgetMs, cost } = body;
    try {
      const out = await adjudicate(facts, budgetMs, cost);
      res.writeHead(200, {"content-type":"application/json"});
      res.end(JSON.stringify(out));
    } catch (err:any){
      res.writeHead(500, {"content-type":"application/json"});
      res.end(JSON.stringify({ error: String(err?.message || err) }));
    }
    return;
  }
  res.writeHead(404); res.end();
});

server.listen(3333, () => console.log("Adjudicator MCP on :3333"));