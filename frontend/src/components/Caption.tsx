interface Props {
  text: string | null;
}

export function Caption({ text }: Props) {
  return (
    <div className="card">
      <div className="section-title">Caption</div>
      <p className="caption-text">{text || "No caption available"}</p>
    </div>
  );
}
