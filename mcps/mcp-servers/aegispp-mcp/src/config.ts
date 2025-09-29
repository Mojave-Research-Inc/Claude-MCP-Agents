import yaml from 'js-yaml';
import fs from 'node:fs';

export type Policy = {
  allow?: string[]; // e.g., ["repo.harvest.plan IF cost_step<2"]
  deny?: string[];
  require?: string[]; // e.g., ["attestations(level>=SLSA2) FOR commit_result"]
};

export interface Config {
  bandit: {
    explore: number;
    alpha: number;
    beta: number;
    gamma: number;
    delta: number;
    confidence_width: number;
  };
  scheduler: {
    market: boolean;
    max_parallel: number;
    timeout_ms: number;
  };
  policy: Policy;
  planner: {
    max_depth: number;
    beam_size: number;
    branch_factor: number;
  };
  verification: {
    enable_contracts: boolean;
    enable_metamorphic: boolean;
    enable_mad_judge: boolean;
    mad_rounds: number;
  };
  attestation: {
    enable: boolean;
    default_level: string;
    key_path?: string;
  };
  mcps: {
    brain_url?: string;
    km_url?: string;
    cs_url?: string;
    rh_url?: string;
    ctx_url?: string;
    resmon_url?: string;
    pgx_url?: string;
  };
}

const DEFAULT_CONFIG: Config = {
  bandit: {
    explore: 0.1,
    alpha: 1.0,
    beta: 1.0,
    gamma: 0.5,
    delta: 0.5,
    confidence_width: 2.0
  },
  scheduler: {
    market: true,
    max_parallel: 4,
    timeout_ms: 300000
  },
  policy: {},
  planner: {
    max_depth: 10,
    beam_size: 3,
    branch_factor: 3
  },
  verification: {
    enable_contracts: true,
    enable_metamorphic: true,
    enable_mad_judge: true,
    mad_rounds: 3
  },
  attestation: {
    enable: true,
    default_level: 'SLSA2'
  },
  mcps: {
    brain_url: process.env.BRAIN_MCP_URL,
    km_url: process.env.KM_MCP_URL,
    cs_url: process.env.CS_MCP_URL,
    rh_url: process.env.RH_MCP_URL,
    ctx_url: process.env.CTX_MCP_URL,
    resmon_url: process.env.RESMON_MCP_URL,
    pgx_url: process.env.PGX_MCP_URL
  }
};

export function loadConfig(): Config {
  const configPath = process.env.AEGIS_CFG;

  if (configPath && fs.existsSync(configPath)) {
    try {
      const loaded = yaml.load(fs.readFileSync(configPath, 'utf8')) as Partial<Config>;
      return mergeConfig(DEFAULT_CONFIG, loaded);
    } catch (error) {
      console.warn(`Failed to load config from ${configPath}:`, error);
    }
  }

  return DEFAULT_CONFIG;
}

function mergeConfig(base: Config, override: Partial<Config>): Config {
  return {
    ...base,
    ...override,
    bandit: { ...base.bandit, ...override.bandit },
    scheduler: { ...base.scheduler, ...override.scheduler },
    policy: { ...base.policy, ...override.policy },
    planner: { ...base.planner, ...override.planner },
    verification: { ...base.verification, ...override.verification },
    attestation: { ...base.attestation, ...override.attestation },
    mcps: { ...base.mcps, ...override.mcps }
  };
}