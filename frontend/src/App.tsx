import { useAnalyze } from "./hooks/useAnalyze";
import { UrlInput } from "./components/UrlInput";
import { LoadingSpinner } from "./components/LoadingSpinner";
import { ErrorBanner } from "./components/ErrorBanner";
import { ReelCard } from "./components/ReelCard";

export default function App() {
  const { data, loading, error, analyze } = useAnalyze();

  return (
    <div className="container">
      <header>
        <h1>Reel Analyzer</h1>
        <p>Paste an Instagram Reel link to extract its metadata</p>
      </header>

      <UrlInput onSubmit={analyze} disabled={loading} />

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}
      {data && <ReelCard data={data} />}
    </div>
  );
}
