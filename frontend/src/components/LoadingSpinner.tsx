export function LoadingSpinner() {
  return (
    <div className="loading">
      <div className="spinner" />
      <p>Opening reel in headless browser...</p>
      <p className="loading-sub">This may take 10-20 seconds</p>
    </div>
  );
}
