import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="min-h-screen bg-gray-900 p-8 text-gray-100">
          <div className="rounded border border-red-800 bg-red-950/40 p-5">
            <h1 className="text-xl font-semibold">Dashboard section failed</h1>
            <p className="mt-2 text-sm text-red-200">{this.state.error.message || 'Unknown render error'}</p>
            <button className="mt-4 rounded bg-gray-700 px-3 py-2" onClick={() => window.location.reload()}>
              Reload dashboard
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
