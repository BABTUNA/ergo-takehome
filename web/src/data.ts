import type { DealBundle, GraphFile } from "./types";

const bundles = new Map<string, DealBundle>();

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export async function loadSlugs(): Promise<string[]> {
  return fetchJson<string[]>("/data/index.json");
}

export async function loadDeal(slug: string): Promise<DealBundle> {
  const cached = bundles.get(slug);
  if (cached) return cached;
  const [graph, events, insights] = await Promise.all([
    fetchJson<DealBundle["graph"]>(`/data/${slug}/graph.json`),
    fetchJson<DealBundle["events"]>(`/data/${slug}/events.json`),
    fetchJson<DealBundle["insights"]>(`/data/${slug}/insights.json`),
  ]);
  const bundle = { slug, graph, events, insights };
  bundles.set(slug, bundle);
  return bundle;
}

export async function loadAllGraphs(): Promise<{ slug: string; graph: GraphFile }[]> {
  const slugs = await loadSlugs();
  return Promise.all(slugs.map(async (slug) => ({
    slug,
    graph: await fetchJson<GraphFile>(`/data/${slug}/graph.json`),
  })));
}
