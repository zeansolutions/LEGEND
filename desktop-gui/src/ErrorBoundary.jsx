import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo });
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#020308] text-red-500 p-10 font-mono flex flex-col gap-4">
          <h1 className="text-2xl font-bold text-red-400">Application Crashed!</h1>
          <p className="text-sm text-slate-300">An unexpected React error occurred.</p>
          <div className="bg-slate-900 p-4 rounded-xl border border-red-900/50 overflow-auto whitespace-pre-wrap text-xs text-red-300">
            {this.state.error && this.state.error.toString()}
            <br />
            {this.state.errorInfo && this.state.errorInfo.componentStack}
          </div>
          <button 
            className="px-4 py-2 bg-red-900/50 hover:bg-red-800/50 text-red-200 border border-red-700/50 rounded-lg w-max transition-colors"
            onClick={() => window.location.reload()}
          >
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children; 
  }
}

export default ErrorBoundary;
