import { createContext, useContext } from 'react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastMessage {
    id: number;
    type: ToastType;
    message: string;
    duration?: number;
}

export interface ToastContextValue {
    showToast: (message: string, type?: ToastType, duration?: number) => void;
    success: (message: string) => void;
    error: (message: string) => void;
    info: (message: string) => void;
    warn: (message: string) => void;
}

export const ToastContext = createContext<ToastContextValue>({
    showToast: () => undefined,
    success: () => undefined,
    error: () => undefined,
    info: () => undefined,
    warn: () => undefined,
});

export function useToast() {
    return useContext(ToastContext);
}
