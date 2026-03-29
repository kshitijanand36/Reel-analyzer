import type { ScrapeResult } from "../types";
import { Caption } from "./Caption";
import { Geotags } from "./Geotags";
import { CommentList } from "./CommentList";

interface Props {
  data: ScrapeResult;
}

export function ReelCard({ data }: Props) {
  return (
    <div className="results">
      {/* Header metadata */}
      <div className="card">
        <div className="meta-row">
          {data.owner && (
            <div className="meta-item">
              @ <span>{data.owner}</span>
            </div>
          )}
          {data.likes != null && (
            <div className="meta-item">
              Likes: <span>{data.likes.toLocaleString()}</span>
            </div>
          )}
          {data.date && (
            <div className="meta-item">
              {data.date}
            </div>
          )}
        </div>
        {data.error && (
          <p className="partial-warning">Partial data — {data.error}</p>
        )}
      </div>

      <Caption text={data.caption} />
      <Geotags locations={data.geotags} />
      <CommentList comments={data.comments} />
    </div>
  );
}
