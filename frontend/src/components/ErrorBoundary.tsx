import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page" style={{ padding: 24 }}>
          <h1>Something went wrong</h1>
          <p className="error">{this.state.error.message}</p>
          <pre className="answer-text">{this.state.error.stack}</pre>
          <p>
            <a href="/dashboard">Back to dashboard</a>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
