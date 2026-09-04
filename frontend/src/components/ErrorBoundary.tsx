// frontend/src/components/ErrorBoundary.tsx
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    state: State = { hasError: false, error: null };

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        if (import.meta.env.DEV) console.error('[ErrorBoundary]', error, info);
        this.props.onError?.(error, info);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback;

            return (
                <div className="error-boundary">
                    <div className="error-boundary-icon"><AlertTriangle size={30} aria-hidden="true" /></div>
                    <h3 className="error-boundary-title">Algo salió mal</h3>
                    <p className="error-boundary-msg">
                        {this.state.error?.message ?? 'Error inesperado en este componente.'}
                    </p>
                    <button type="button" className="error-boundary-reset" onClick={this.handleReset}>
                        <RefreshCw size={16} aria-hidden="true" /> Reintentar
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
