import { api } from "../api";
import type { DirectoryListing } from "../types";

const cache = new Map<string, { value: DirectoryListing; expires: number }>();
const pending = new Map<string, symbol>();
const TTL = 10_000;
const LIMIT = 20;
export async function directoryListing(path: string, refresh = false): Promise<DirectoryListing> {
  const hit = cache.get(path);
  if (!refresh && hit && hit.expires > Date.now()) {
    cache.delete(path);
    cache.set(path, hit);
    return hit.value;
  }
  const token = Symbol(path);
  pending.set(path, token);
  let value: DirectoryListing;
  try { value = await api.filesystem(path); }
  catch (error) { if (pending.get(path) === token) pending.delete(path); throw error; }
  if (pending.get(path) !== token) return value;
  pending.delete(path);
  cache.delete(path);
  cache.set(path, { value, expires: Date.now() + TTL });
  while (cache.size > LIMIT) cache.delete(cache.keys().next().value!);
  return value;
}
