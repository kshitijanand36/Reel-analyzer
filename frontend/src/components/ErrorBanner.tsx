interface Props {
  message: string;
}

export function ErrorBanner({ message }: Props) {
  return <div className="error">{message}</div>;
}
