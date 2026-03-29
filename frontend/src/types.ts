export interface Comment {
  user: string;
  text: string;
}

export interface ScrapeResult {
  caption: string | null;
  geotags: string[];
  comments: Comment[];
  owner: string | null;
  likes: number | null;
  date: string | null;
  error: string | null;
}
