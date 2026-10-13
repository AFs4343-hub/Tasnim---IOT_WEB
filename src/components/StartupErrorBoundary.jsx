import { Component } from 'react'
import SetupNotice from './SetupNotice.jsx'

export default class StartupErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    console.error('TAS[N]IM gagal dimulai:', error?.message ?? error)
  }

  render() {
    return this.state.error ? <SetupNotice error={this.state.error} /> : this.props.children
  }
}
