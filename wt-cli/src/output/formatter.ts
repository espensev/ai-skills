import chalk from 'chalk';
import { getTerminalWidth } from '../platform/detect.js';

export interface Column {
  key: string;
  label: string;
  width?: number;
  align?: 'left' | 'right';
  color?: (value: string) => string;
}

export function formatTable(columns: Column[], rows: Record<string, string>[]): string {
  if (rows.length === 0) return '';

  // Calculate column widths
  const widths = columns.map((col) => {
    const maxContent = Math.max(
      col.label.length,
      ...rows.map((r) => (r[col.key] ?? '').length),
    );
    return col.width ?? maxContent;
  });

  const termWidth = getTerminalWidth();
  const totalWidth = widths.reduce((sum, w) => sum + w + 2, 0);

  // Truncate last column if needed
  if (totalWidth > termWidth && widths.length > 0) {
    widths[widths.length - 1] = Math.max(
      10,
      widths[widths.length - 1] - (totalWidth - termWidth),
    );
  }

  const lines: string[] = [];

  // Header
  const header = columns
    .map((col, i) => pad(col.label, widths[i], col.align))
    .join('  ');
  lines.push(chalk.bold(header));

  // Separator
  lines.push(widths.map((w) => '─'.repeat(w)).join('  '));

  // Rows
  for (const row of rows) {
    const line = columns
      .map((col, i) => {
        const value = truncate(row[col.key] ?? '', widths[i]);
        const padded = pad(value, widths[i], col.align);
        return col.color ? col.color(padded) : padded;
      })
      .join('  ');
    lines.push(line);
  }

  return lines.join('\n');
}

function pad(text: string, width: number, align: 'left' | 'right' = 'left'): string {
  if (text.length >= width) return text.slice(0, width);
  const padding = ' '.repeat(width - text.length);
  return align === 'right' ? padding + text : text + padding;
}

function truncate(text: string, maxWidth: number): string {
  if (text.length <= maxWidth) return text;
  return text.slice(0, maxWidth - 1) + '…';
}
