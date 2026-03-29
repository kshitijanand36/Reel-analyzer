interface Props {
  locations: string[];
}

export function Geotags({ locations }: Props) {
  if (locations.length === 0) return null;

  return (
    <div className="card">
      <div className="section-title">Location</div>
      <div className="geotag-list">
        {locations.map((loc, i) => (
          <span key={i} className="geotag-badge">
            {loc}
          </span>
        ))}
      </div>
    </div>
  );
}
