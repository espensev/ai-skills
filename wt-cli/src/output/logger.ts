import chalk from 'chalk';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

let currentLevel: LogLevel = 'info';

const levelOrder: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export function setLogLevel(level: LogLevel): void {
  currentLevel = level;
}

function shouldLog(level: LogLevel): boolean {
  return levelOrder[level] >= levelOrder[currentLevel];
}

export function debug(message: string): void {
  if (shouldLog('debug')) {
    console.error(chalk.gray(`[debug] ${message}`));
  }
}

export function info(message: string): void {
  if (shouldLog('info')) {
    console.error(message);
  }
}

export function warn(message: string): void {
  if (shouldLog('warn')) {
    console.error(chalk.yellow(`warning: ${message}`));
  }
}

export function error(message: string): void {
  if (shouldLog('error')) {
    console.error(chalk.red(`error: ${message}`));
  }
}

export function success(message: string): void {
  if (shouldLog('info')) {
    console.error(chalk.green(message));
  }
}
