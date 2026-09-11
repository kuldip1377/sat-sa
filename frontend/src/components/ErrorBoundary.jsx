import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { err: null } }
  static getDerivedStateFromError(err) { return { err } }
  render() {
    if (this.state.err) {
      return (
        <div className="p-10 text-center">
          <div className="text-red-400 font-semibold mb-2">Console view crashed</div>
          <div className="text-xs text-slate-500 mb-4">{String(this.state.err)}</div>
          <button onClick={() => this.setState({ err: null })}
            className="rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white">
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
