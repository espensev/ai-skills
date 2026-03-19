export function outputJson(data: unknown): void {
  console.log(JSON.stringify(data, null, 2));
}

export function outputJsonError(message: string, code: string): void {
  console.log(JSON.stringify({ error: message, code }, null, 2));
}
