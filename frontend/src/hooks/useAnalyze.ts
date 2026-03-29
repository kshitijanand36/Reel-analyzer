import { useState } from "react";
import type { ScrapeResult } from "../types";

export function useAnalyze() {
  const [data, setData] = useState<ScrapeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(url: string) {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "Scraping failed");
      }

      const result: ScrapeResult = await res.json();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return { data, loading, error, analyze };
}
