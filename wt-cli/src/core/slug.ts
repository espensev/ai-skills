export function toWorktreeSlug(value: string): string {
  let slug = value.toLowerCase();
  slug = slug.replace(/[^a-z0-9._-]+/g, '-');
  slug = slug.replace(/^-+|-+$/g, '');

  if (!slug) {
    throw new Error(`Unable to derive a valid worktree name from '${value}'.`);
  }

  return slug;
}
