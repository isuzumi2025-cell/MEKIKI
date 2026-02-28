/**
 * @icc/rag-engine
 * Phase 4: RAG engine for ObsidianVault semantic search
 *
 * Usage:
 *   const engine = new RAGEngine({ vaultPath: "/path/to/ObsidianVault" });
 *   await engine.index();
 *   const results = await engine.search("MEKIKI校正の手順");
 */

export interface VaultNote {
  path: string;
  title: string;
  content: string;
  tags: string[];
  excerpt: string;
  embedding?: number[];
}

export interface SearchResult {
  note: VaultNote;
  score: number;
}

export interface RAGEngineOptions {
  vaultPath: string;
  embeddingProvider?: "gemini";
  topK?: number;
}

/**
 * RAGEngine — Phase 4 implementation stub.
 * Full vector indexing + semantic search to be implemented in Phase 4.
 */
export class RAGEngine {
  private vaultPath: string;
  private topK: number;
  private notes: VaultNote[] = [];
  private indexed = false;

  constructor(options: RAGEngineOptions) {
    this.vaultPath = options.vaultPath;
    this.topK = options.topK ?? 5;
  }

  /**
   * Index all markdown files in the vault.
   * Phase 4: adds embedding computation.
   */
  async index(): Promise<void> {
    // Phase 4: scan vault files, compute embeddings, store in index
    console.log(`[RAGEngine] Indexing vault at ${this.vaultPath} (Phase 4 stub)`);
    this.indexed = true;
  }

  /**
   * Simple text search (fallback when embeddings not available).
   */
  textSearch(query: string, notes: VaultNote[]): SearchResult[] {
    const q = query.toLowerCase();
    return notes
      .filter(
        (n) =>
          n.title.toLowerCase().includes(q) ||
          n.content.toLowerCase().includes(q) ||
          n.tags.some((t) => t.toLowerCase().includes(q))
      )
      .map((n) => ({
        note: n,
        score: n.title.toLowerCase().includes(q) ? 0.9 : 0.5,
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, this.topK);
  }

  async search(query: string): Promise<SearchResult[]> {
    if (!this.indexed) {
      await this.index();
    }
    return this.textSearch(query, this.notes);
  }
}

export { RAGEngine as default };
