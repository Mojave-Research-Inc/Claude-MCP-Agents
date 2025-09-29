import { spawn, ChildProcess } from 'node:child_process';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { logger } from '../logger.js';
import { now } from '../ids.js';

export interface SandboxConfig {
  isolateNetwork?: boolean;
  isolateFilesystem?: boolean;
  allowedPaths?: string[];
  blockedPaths?: string[];
  resourceLimits?: {
    maxMemoryMB?: number;
    maxCpuPercent?: number;
    maxDurationMs?: number;
  };
  environment?: Record<string, string>;
}

export interface SandboxResult {
  success: boolean;
  outputs: any;
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  duration_ms: number;
  resourceUsage?: {
    maxMemoryMB: number;
    cpuTimeMs: number;
  };
  violations?: string[];
}

export class SandboxedExecutor {
  private tempDir: string;
  private activeSandboxes: Map<string, ChildProcess> = new Map();

  constructor(tempDir: string = '/tmp/aegis-sandbox') {
    this.tempDir = tempDir;
  }

  async execute(
    command: string,
    args: string[],
    inputs: any,
    config: SandboxConfig = {}
  ): Promise<SandboxResult> {
    const sandboxId = `sandbox_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = now();

    try {
      // Create isolated workspace
      const workspaceDir = await this.createWorkspace(sandboxId, inputs);

      // Prepare sandboxed command
      const sandboxedCommand = await this.prepareSandboxedCommand(
        command,
        args,
        workspaceDir,
        config
      );

      // Execute in sandbox
      const result = await this.executeSandboxed(
        sandboxId,
        sandboxedCommand.command,
        sandboxedCommand.args,
        sandboxedCommand.options,
        config
      );

      // Collect outputs
      const outputs = await this.collectOutputs(workspaceDir, config);

      // Cleanup workspace
      await this.cleanupWorkspace(workspaceDir);

      return {
        success: result.exitCode === 0,
        outputs,
        stdout: result.stdout,
        stderr: result.stderr,
        exitCode: result.exitCode,
        duration_ms: now() - startTime,
        resourceUsage: result.resourceUsage,
        violations: result.violations
      };
    } catch (error) {
      logger.error(`Sandbox execution failed for ${sandboxId}:`, error);
      return {
        success: false,
        outputs: {},
        stderr: error.message,
        duration_ms: now() - startTime,
        violations: ['execution_error']
      };
    } finally {
      this.activeSandboxes.delete(sandboxId);
    }
  }

  private async createWorkspace(sandboxId: string, inputs: any): Promise<string> {
    const workspaceDir = path.join(this.tempDir, sandboxId);

    try {
      await fs.mkdir(workspaceDir, { recursive: true });

      // Create input files
      if (inputs.files) {
        for (const [filename, content] of Object.entries(inputs.files)) {
          const filePath = path.join(workspaceDir, filename as string);
          const fileDir = path.dirname(filePath);
          await fs.mkdir(fileDir, { recursive: true });
          await fs.writeFile(filePath, content as string);
        }
      }

      // Create inputs.json
      await fs.writeFile(
        path.join(workspaceDir, 'inputs.json'),
        JSON.stringify(inputs, null, 2)
      );

      logger.debug(`Created sandbox workspace: ${workspaceDir}`);
      return workspaceDir;
    } catch (error) {
      logger.error(`Failed to create workspace ${workspaceDir}:`, error);
      throw error;
    }
  }

  private async prepareSandboxedCommand(
    command: string,
    args: string[],
    workspaceDir: string,
    config: SandboxConfig
  ): Promise<{ command: string; args: string[]; options: any }> {
    // For demonstration, we'll use a simple chroot-like approach
    // In production, you'd use proper containerization (Docker/Podman) or namespaces

    const sandboxCommand = 'timeout';
    const timeoutSeconds = Math.ceil((config.resourceLimits?.maxDurationMs || 60000) / 1000);

    const sandboxArgs = [
      `${timeoutSeconds}s`, // Timeout
      command,
      ...args
    ];

    const options = {
      cwd: workspaceDir,
      env: {
        ...this.createSandboxEnvironment(config),
        PATH: '/usr/bin:/bin', // Restricted PATH
        HOME: workspaceDir,
        TMPDIR: workspaceDir
      },
      // Additional security options would go here
      uid: process.getuid ? process.getuid() : undefined,
      gid: process.getgid ? process.getgid() : undefined
    };

    return { command: sandboxCommand, args: sandboxArgs, options };
  }

  private createSandboxEnvironment(config: SandboxConfig): Record<string, string> {
    const env = {
      // Minimal environment
      PATH: '/usr/bin:/bin',
      LANG: 'C.UTF-8',
      // Remove potentially dangerous variables
      LD_PRELOAD: '',
      LD_LIBRARY_PATH: '',
    };

    // Add allowed environment variables
    if (config.environment) {
      Object.assign(env, config.environment);
    }

    return env;
  }

  private async executeSandboxed(
    sandboxId: string,
    command: string,
    args: string[],
    options: any,
    config: SandboxConfig
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      let stdout = '';
      let stderr = '';
      const violations: string[] = [];

      const child = spawn(command, args, options);
      this.activeSandboxes.set(sandboxId, child);

      // Monitor resource usage (simplified)
      const resourceMonitor = this.startResourceMonitoring(child, config, violations);

      child.stdout?.on('data', (data) => {
        stdout += data.toString();
        // Check for policy violations in output
        this.checkOutputViolations(data.toString(), violations);
      });

      child.stderr?.on('data', (data) => {
        stderr += data.toString();
        this.checkOutputViolations(data.toString(), violations);
      });

      child.on('close', (code, signal) => {
        clearInterval(resourceMonitor);
        const duration = Date.now() - startTime;

        resolve({
          exitCode: code,
          signal,
          stdout,
          stderr,
          duration,
          resourceUsage: this.getResourceUsage(child),
          violations
        });
      });

      child.on('error', (error) => {
        clearInterval(resourceMonitor);
        reject(error);
      });

      // Set up timeout
      const timeout = config.resourceLimits?.maxDurationMs || 60000;
      setTimeout(() => {
        if (!child.killed) {
          violations.push('execution_timeout');
          child.kill('SIGKILL');
        }
      }, timeout);
    });
  }

  private startResourceMonitoring(
    child: ChildProcess,
    config: SandboxConfig,
    violations: string[]
  ): NodeJS.Timeout {
    let maxMemory = 0;
    let cpuTime = 0;

    return setInterval(async () => {
      try {
        if (child.pid) {
          const stats = await this.getProcessStats(child.pid);

          maxMemory = Math.max(maxMemory, stats.memoryMB);
          cpuTime += stats.cpuPercent;

          // Check limits
          if (config.resourceLimits?.maxMemoryMB && stats.memoryMB > config.resourceLimits.maxMemoryMB) {
            violations.push('memory_limit_exceeded');
            child.kill('SIGKILL');
          }

          if (config.resourceLimits?.maxCpuPercent && stats.cpuPercent > config.resourceLimits.maxCpuPercent) {
            violations.push('cpu_limit_exceeded');
          }
        }
      } catch (error) {
        // Process might have exited
      }
    }, 1000);
  }

  private async getProcessStats(pid: number): Promise<{ memoryMB: number; cpuPercent: number }> {
    try {
      // Read from /proc/[pid]/status and /proc/[pid]/stat
      // This is a simplified version - in production you'd use proper monitoring
      const statData = await fs.readFile(`/proc/${pid}/stat`, 'utf8');
      const statusData = await fs.readFile(`/proc/${pid}/status`, 'utf8');

      // Extract memory usage (simplified)
      const vmRssMatch = statusData.match(/VmRSS:\s+(\d+)\s+kB/);
      const memoryKB = vmRssMatch ? parseInt(vmRssMatch[1]) : 0;
      const memoryMB = memoryKB / 1024;

      // Extract CPU usage (simplified)
      const statFields = statData.trim().split(' ');
      const utime = parseInt(statFields[13] || '0');
      const stime = parseInt(statFields[14] || '0');
      const cpuPercent = (utime + stime) / 100; // Simplified calculation

      return { memoryMB, cpuPercent };
    } catch (error) {
      return { memoryMB: 0, cpuPercent: 0 };
    }
  }

  private getResourceUsage(child: ChildProcess): any {
    // In a real implementation, you'd collect actual resource usage
    return {
      maxMemoryMB: 0,
      cpuTimeMs: 0
    };
  }

  private checkOutputViolations(output: string, violations: string[]): void {
    const policyViolations = [
      { pattern: /password|secret|key|token/i, violation: 'sensitive_data_exposure' },
      { pattern: /rm -rf|del \/|format c:/i, violation: 'destructive_command' },
      { pattern: /curl|wget|nc |netcat/i, violation: 'network_access_attempt' },
      { pattern: /sudo|su -|chmod 777/i, violation: 'privilege_escalation_attempt' }
    ];

    for (const rule of policyViolations) {
      if (rule.pattern.test(output) && !violations.includes(rule.violation)) {
        violations.push(rule.violation);
      }
    }
  }

  private async collectOutputs(workspaceDir: string, config: SandboxConfig): Promise<any> {
    const outputs: any = {};

    try {
      // Check for outputs.json
      const outputsPath = path.join(workspaceDir, 'outputs.json');
      try {
        const outputsContent = await fs.readFile(outputsPath, 'utf8');
        outputs.structured = JSON.parse(outputsContent);
      } catch (error) {
        // No structured outputs
      }

      // Collect created files (if allowed)
      if (!config.isolateFilesystem) {
        const files = await this.collectFiles(workspaceDir);
        if (Object.keys(files).length > 0) {
          outputs.files = files;
        }
      }

      return outputs;
    } catch (error) {
      logger.warn(`Failed to collect outputs from ${workspaceDir}:`, error);
      return {};
    }
  }

  private async collectFiles(dir: string): Promise<Record<string, string>> {
    const files: Record<string, string> = {};

    try {
      const entries = await fs.readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        if (entry.isFile() && entry.name !== 'inputs.json') {
          const filePath = path.join(dir, entry.name);
          const content = await fs.readFile(filePath, 'utf8');
          files[entry.name] = content;
        }
      }
    } catch (error) {
      logger.warn(`Failed to collect files from ${dir}:`, error);
    }

    return files;
  }

  private async cleanupWorkspace(workspaceDir: string): Promise<void> {
    try {
      await fs.rm(workspaceDir, { recursive: true, force: true });
      logger.debug(`Cleaned up workspace: ${workspaceDir}`);
    } catch (error) {
      logger.warn(`Failed to cleanup workspace ${workspaceDir}:`, error);
    }
  }

  async killSandbox(sandboxId: string): Promise<boolean> {
    const process = this.activeSandboxes.get(sandboxId);
    if (process && !process.killed) {
      process.kill('SIGTERM');
      // Give it a moment to clean up, then force kill
      setTimeout(() => {
        if (!process.killed) {
          process.kill('SIGKILL');
        }
      }, 5000);
      return true;
    }
    return false;
  }

  getActiveSandboxes(): string[] {
    return Array.from(this.activeSandboxes.keys());
  }

  async createDockerSandbox(
    image: string,
    command: string[],
    inputs: any,
    config: SandboxConfig
  ): Promise<SandboxResult> {
    // Alternative implementation using Docker/Podman
    const sandboxId = `docker_${Date.now()}`;
    const startTime = now();

    try {
      const workspaceDir = await this.createWorkspace(sandboxId, inputs);

      const dockerArgs = [
        'run',
        '--rm',
        '--network=none', // Isolate network
        `--memory=${config.resourceLimits?.maxMemoryMB || 256}m`,
        `--cpus=${(config.resourceLimits?.maxCpuPercent || 50) / 100}`,
        `--volume=${workspaceDir}:/workspace:rw`,
        '--workdir=/workspace',
        '--user=1000:1000', // Non-root user
        image,
        ...command
      ];

      const result = await this.executeSandboxed(
        sandboxId,
        'docker', // or 'podman'
        dockerArgs,
        { cwd: workspaceDir },
        config
      );

      const outputs = await this.collectOutputs(workspaceDir, config);
      await this.cleanupWorkspace(workspaceDir);

      return {
        success: result.exitCode === 0,
        outputs,
        stdout: result.stdout,
        stderr: result.stderr,
        exitCode: result.exitCode,
        duration_ms: now() - startTime,
        resourceUsage: result.resourceUsage,
        violations: result.violations
      };
    } catch (error) {
      logger.error(`Docker sandbox execution failed:`, error);
      return {
        success: false,
        outputs: {},
        stderr: error.message,
        duration_ms: now() - startTime,
        violations: ['docker_execution_error']
      };
    }
  }
}

export const sandboxExecutor = new SandboxedExecutor();