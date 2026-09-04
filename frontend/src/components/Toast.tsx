import { useCallback, useEffect, useRef, useState } from 'react';
import { ToastContext } from './toastContext';
import type { ToastMessage, ToastType } from './toastContext';

let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastMessage[]>([]);

    const remove = useCallback((id: number) => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
    }, []);

    const showToast = useCallback((message: string, type: ToastType = 'info', duration = 3500) => {
        const id = nextId++;
        setToasts((current) => [...current.slice(-4), { id, type, message, duration }]);
        window.setTimeout(() => remove(id), duration);
    }, [remove]);

    const success = useCallback((message: string) => showToast(message, 'success'), [showToast]);
    const error = useCallback((message: string) => showToast(message, 'error', 5000), [showToast]);
    const info = useCallback((message: string) => showToast(message, 'info'), [showToast]);
    const warn = useCallback((message: string) => showToast(message, 'warning'), [showToast]);

    return (
        <ToastContext.Provider value={{ showToast, success, error, info, warn }}>
            {children}
            <ToastContainer toasts={toasts} onDismiss={remove} />
        </ToastContext.Provider>
    );
}

const ICONS: Record<ToastType, string> = {
    success: '✓',
    error: '!',
    info: 'i',
    warning: '△',
};

function ToastContainer({ toasts, onDismiss }: { toasts: ToastMessage[]; onDismiss: (id: number) => void }) {
    if (toasts.length === 0) return null;
    return (
        <div className="toast-container" role="region" aria-label="Notificaciones">
            {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />)}
        </div>
    );
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: (id: number) => void }) {
    const [visible, setVisible] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const frame = requestAnimationFrame(() => setVisible(true));
        timerRef.current = setTimeout(() => setVisible(false), (toast.duration ?? 3500) - 300);
        return () => {
            cancelAnimationFrame(frame);
            if (timerRef.current !== null) clearTimeout(timerRef.current);
        };
    }, [toast.duration]);

    return (
        <div className={`toast toast--${toast.type} ${visible ? 'toast--visible' : ''}`} role="status" aria-live={toast.type === 'error' ? 'assertive' : 'polite'}>
            <span className="toast-icon" aria-hidden="true">{ICONS[toast.type]}</span>
            <span className="toast-message">{toast.message}</span>
            <button type="button" className="toast-dismiss" onClick={() => onDismiss(toast.id)} aria-label="Cerrar notificación">×</button>
        </div>
    );
}
