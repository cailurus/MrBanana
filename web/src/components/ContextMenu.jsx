import React from 'react';
import { createPortal } from 'react-dom';
import { Play, Pause } from 'lucide-react';

/**
 * Context menu for download tasks
 */
export function ContextMenu({
    contextMenu,
    onClose,
    onResume,
    onPause,
    onDelete,
    tr
}) {
    if (!contextMenu) return null;

    return createPortal(
        <div
            className="fixed z-50 min-w-40 rounded-md border bg-popover p-1 text-sm text-popover-foreground shadow-sm"
            style={{ left: contextMenu.x, top: contextMenu.y }}
            onClick={(e) => e.stopPropagation()}
            onContextMenu={(e) => e.preventDefault()}
        >
            {contextMenu.item?.status === 'Paused' && (
                <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-2 hover:bg-accent"
                    onClick={() => {
                        onResume(contextMenu.item.id);
                        onClose();
                    }}
                >
                    <Play className="h-4 w-4" />
                    {tr('download.menu.resume')}
                </button>
            )}

            {(contextMenu.item?.status === 'Downloading' || contextMenu.item?.status === 'Preparing') && (
                <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-2 hover:bg-accent"
                    onClick={() => {
                        onPause(contextMenu.item.id);
                        onClose();
                    }}
                >
                    <Pause className="h-4 w-4" />
                    {tr('download.menu.pause')}
                </button>
            )}

            <button
                type="button"
                className="flex w-full items-center gap-2 rounded-sm px-2 py-2 hover:bg-accent"
                onClick={() => {
                    onDelete(contextMenu.item.id);
                    onClose();
                }}
            >
                <span className="inline-block h-4 w-4 text-center leading-4">×</span>
                {tr('common.delete')}
            </button>
        </div>,
        document.body
    );
}

export default ContextMenu;
