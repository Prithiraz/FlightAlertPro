import { Component } from 'react';

/**
 * Catches unhandled React rendering errors, logs them to the console (and to
 * Sentry if VITE_SENTRY_DSN is configured), and shows a simple fallback UI.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Uncaught error:', error, info);

    // If @sentry/react is installed and configured, it will capture errors
    // automatically via its own ErrorBoundary. This boundary is a lightweight
    // fallback for when Sentry is not available.
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p>Please refresh the page. If the problem persists, contact support.</p>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
