// Keeps a chart's exception inside its card. Without it, an error thrown while Highcharts draws (an option it
// rejects, say) unmounts the whole React tree and leaves a blank page, losing every selection on it.

import React from 'react';

interface Props { title: string; children: React.ReactNode }
interface State { failed: boolean }

export default class ChartErrorBoundary extends React.Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error(`[charts] ${this.props.title} couldn't be drawn:`, error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="py-6 text-center text-sm text-gray-700">
        <p className="mb-2 font-semibold">{this.props.title}: this chart couldn&apos;t be drawn.</p>
        <button type="button" onClick={() => this.setState({ failed: false })}
          className="rounded border border-gray-300 px-3 py-1 font-medium hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
          Try again
        </button>
      </div>
    );
  }
}
