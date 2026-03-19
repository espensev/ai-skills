export interface SpawnOptions {
  branchPrefix: string;
  base: string;
  path?: string;
  port?: number;
  scope?: string;
  detached: boolean;
  skipInstall: boolean;
  skipEnv: boolean;
  skipBootstrap: boolean;
  json: boolean;
}

export interface ListOptions {
  all: boolean;
  json: boolean;
}

export interface MergeOptions {
  target?: string;
  all: boolean;
  dryRun: boolean;
  deleteBranch: boolean;
  json: boolean;
}

export interface TeardownOptions {
  force: boolean;
  deleteBranch: boolean;
  all: boolean;
  json: boolean;
}

export interface BootstrapOptions {
  port?: number;
  scope?: string;
  skipInstall: boolean;
  skipEnv: boolean;
  json: boolean;
}

export interface DiffOptions {
  target?: string;
  json: boolean;
}
