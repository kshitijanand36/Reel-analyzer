import type { Comment } from "../types";

interface Props {
  comments: Comment[];
}

export function CommentList({ comments }: Props) {
  if (comments.length === 0) {
    return (
      <div className="card">
        <div className="section-title">Comments</div>
        <p className="no-data">No comments extracted</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="section-title">Comments ({comments.length})</div>
      <ul className="comment-list">
        {comments.map((c, i) => (
          <li key={i}>
            <span className="comment-user">@{c.user}</span>
            <span className="comment-text">{c.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
