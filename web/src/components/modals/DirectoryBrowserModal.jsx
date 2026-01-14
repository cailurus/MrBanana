import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { X, Folder, FolderOpen, ChevronUp, Home, Loader2, AlertCircle, File } from 'lucide-react';

/**
 * Directory Browser Modal for remote directory selection
 * Used when the native file dialog is not available (non-localhost access)
 * 
 * @param {Function} tr - Translation function (key, vars) => string, optional
 */
export default function DirectoryBrowserModal({ isOpen, onClose, onSelect, title, initialDir, tr }) {
    // Fallback translation function if none provided
    const translate = tr || ((key) => {
        const fallbacks = {
            'directoryBrowser.title': 'Choose Directory',
            'directoryBrowser.selectRoot': 'Select an available root directory:',
            'directoryBrowser.up': 'Up',
            'directoryBrowser.roots': 'Roots',
            'directoryBrowser.empty': 'This directory is empty',
            'directoryBrowser.selectThis': 'Select This',
            'directoryBrowser.errorFetchingRoots': 'Failed to fetch available directories',
            'directoryBrowser.errorListing': 'Failed to list directory contents',
            'common.cancel': 'Cancel',
        };
        return fallbacks[key] || key;
    });

    const [roots, setRoots] = useState([]);
    const [currentPath, setCurrentPath] = useState('');
    const [parentPath, setParentPath] = useState(null);
    const [directories, setDirectories] = useState([]);
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Fetch allowed root directories
    const fetchRoots = useCallback(async () => {
        try {
            const res = await axios.get('/api/system/browse-roots');
            setRoots(res.data.roots || []);
            return res.data.roots || [];
        } catch (err) {
            setError(translate('directoryBrowser.errorFetchingRoots'));
            return [];
        }
    }, [translate]);

    // List directory contents
    const listDirectory = useCallback(async (path) => {
        setLoading(true);
        setError('');
        try {
            const res = await axios.post('/api/system/list-directory', { path });
            setCurrentPath(res.data.current);
            setParentPath(res.data.parent);
            setDirectories(res.data.directories || []);
            setFiles(res.data.files || []);
        } catch (err) {
            const msg = err.response?.data?.detail || translate('directoryBrowser.errorListing');
            setError(msg);
            setDirectories([]);
            setFiles([]);
        } finally {
            setLoading(false);
        }
    }, [translate]);

    // Initialize on open
    useEffect(() => {
        if (isOpen) {
            setError('');
            setCurrentPath('');
            setParentPath(null);
            setDirectories([]);
            setFiles([]);

            fetchRoots().then((fetchedRoots) => {
                // If initialDir is provided and valid, navigate to it
                if (initialDir) {
                    listDirectory(initialDir).catch(() => {
                        // If initialDir fails, show roots
                        if (fetchedRoots.length === 1) {
                            listDirectory(fetchedRoots[0].path);
                        }
                    });
                } else if (fetchedRoots.length === 1) {
                    // If only one root, auto-navigate to it
                    listDirectory(fetchedRoots[0].path);
                }
            });
        }
    }, [isOpen, initialDir, fetchRoots, listDirectory]);

    const handleSelectCurrent = () => {
        if (currentPath) {
            onSelect(currentPath);
            onClose();
        }
    };

    const handleNavigateUp = () => {
        if (parentPath) {
            listDirectory(parentPath);
        }
    };

    const handleSelectRoot = (root) => {
        listDirectory(root.path);
    };

    const handleSelectDir = (dir) => {
        listDirectory(dir.path);
    };

    if (!isOpen) return null;

    const showRootSelection = !currentPath && roots.length > 0;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
                    <h2 className="text-lg font-semibold text-white">
                        {title || translate('directoryBrowser.title')}
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-1 rounded hover:bg-gray-700 transition-colors"
                    >
                        <X className="w-5 h-5 text-gray-400" />
                    </button>
                </div>

                {/* Current Path Display */}
                {currentPath && (
                    <div className="px-4 py-2 bg-gray-750 border-b border-gray-700 flex items-center gap-2">
                        <Folder className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                        <span className="text-sm text-gray-300 truncate font-mono">
                            {currentPath}
                        </span>
                    </div>
                )}

                {/* Navigation Toolbar */}
                {currentPath && (
                    <div className="px-4 py-2 border-b border-gray-700 flex gap-2">
                        <button
                            onClick={handleNavigateUp}
                            disabled={!parentPath}
                            className="flex items-center gap-1 px-2 py-1 text-sm rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronUp className="w-4 h-4" />
                            {translate('directoryBrowser.up')}
                        </button>
                        <button
                            onClick={() => {
                                setCurrentPath('');
                                setParentPath(null);
                                setDirectories([]);
                            }}
                            className="flex items-center gap-1 px-2 py-1 text-sm rounded bg-gray-700 hover:bg-gray-600 transition-colors"
                        >
                            <Home className="w-4 h-4" />
                            {translate('directoryBrowser.roots')}
                        </button>
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto min-h-[200px] max-h-[400px]">
                    {loading ? (
                        <div className="flex items-center justify-center h-full py-8">
                            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center h-full py-8 text-red-400">
                            <AlertCircle className="w-8 h-8 mb-2" />
                            <span className="text-sm text-center px-4">{error}</span>
                        </div>
                    ) : showRootSelection ? (
                        /* Root Selection */
                        <div className="p-4">
                            <p className="text-sm text-gray-400 mb-3">
                                {translate('directoryBrowser.selectRoot')}
                            </p>
                            <div className="space-y-2">
                                {roots.map((root, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSelectRoot(root)}
                                        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors text-left"
                                    >
                                        <FolderOpen className="w-5 h-5 text-yellow-500 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm font-medium text-white truncate">
                                                {root.name}
                                            </div>
                                            <div className="text-xs text-gray-400 truncate font-mono">
                                                {root.path}
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (directories.length === 0 && files.length === 0) ? (
                        <div className="flex items-center justify-center h-full py-8 text-gray-500">
                            <span className="text-sm">{translate('directoryBrowser.empty')}</span>
                        </div>
                    ) : (
                        /* Directory and File Listing */
                        <div className="p-2">
                            {/* Directories - clickable to navigate */}
                            {directories.map((dir, idx) => (
                                <button
                                    key={`dir-${idx}`}
                                    onClick={() => handleSelectDir(dir)}
                                    className="w-full flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-700 transition-colors text-left"
                                >
                                    <Folder className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                                    <span className="text-sm text-gray-200 truncate">
                                        {dir.name}
                                    </span>
                                </button>
                            ))}
                            {/* Files - display only, not clickable */}
                            {files.map((file, idx) => (
                                <div
                                    key={`file-${idx}`}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-left opacity-60"
                                >
                                    <File className="w-4 h-4 text-gray-400 flex-shrink-0" />
                                    <span className="text-sm text-gray-400 truncate">
                                        {file.name}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-4 py-3 border-t border-gray-700 flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
                    >
                        {translate('common.cancel')}
                    </button>
                    <button
                        onClick={handleSelectCurrent}
                        disabled={!currentPath}
                        className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {translate('directoryBrowser.selectThis')}
                    </button>
                </div>
            </div>
        </div>
    );
}
