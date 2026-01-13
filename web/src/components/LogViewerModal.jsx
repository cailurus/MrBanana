import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { Card } from './ui';

/**
 * Log viewer modal component
 */
export function LogViewerModal({
    open,
    onClose,
    logViewer,
    logText,
    logExists,
    logEndRef,
    tr
}) {
    if (!open) return null;

    return createPortal(
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
        >
            <div
                className="w-full max-w-5xl px-4"
                onClick={(e) => e.stopPropagation()}
            >
                <Card className="p-4">
                    <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-medium text-foreground whitespace-nowrap">
                            {tr('log.title', { id: logViewer.id })}
                        </div>
                        <button
                            type="button"
                            className="inline-flex items-center justify-center rounded-md px-2 py-1 text-sm hover:bg-accent hover:text-accent-foreground text-muted-foreground"
                            onClick={onClose}
                        >
                            {tr('common.close')}
                        </button>
                    </div>

                    <div className="mt-3 h-[22rem] overflow-auto rounded-md border bg-background p-3">
                        {!logExists ? (
                            <div className="text-sm text-muted-foreground">{tr('log.empty')}</div>
                        ) : (
                            <pre className="whitespace-pre-wrap break-all text-xs text-foreground">
                                {logText || ''}
                                <span ref={logEndRef} />
                            </pre>
                        )}
                    </div>
                </Card>
            </div>
        </div>,
        document.body
    );
}

export default LogViewerModal;
