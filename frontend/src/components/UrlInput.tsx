import { useState } from "react";

interface Props {
  onSubmit: (url: string) => void;
  disabled: boolean;
}

export function UrlInput({ onSubmit, disabled }: Props) {
  const [url, setUrl] = useState("");

  const handleSubmit = () => {
    if (url.trim()) onSubmit(url.trim());
  };

  return (
    <div className="input-section">
      <input
        type="text"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        placeholder="https://www.instagram.com/reel/..."
        disabled={disabled}
      />
      <button onClick={handleSubmit} disabled={disabled || !url.trim()}>
        Scrape
      </button>
    </div>
  );
}
