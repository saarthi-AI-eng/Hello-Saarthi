import { useState, useCallback } from 'react';
import { Upload, File as FileIcon, X } from 'lucide-react';
import { uploadFile } from '../lib/api';
import './FileDropzone.css';

interface FileDropzoneProps {
    /** When mode is 'upload', uploads on drop and calls onUploaded(url). When 'select', just calls onFileSelected(file) for parent to upload later. */
    mode?: 'upload' | 'select';
    onUploaded?: (url: string, file: File) => void;
    onFileSelected?: (file: File | null) => void;
    onClear?: () => void;
    currentFile?: File | null;
    currentUrl?: string | null;
    disabled?: boolean;
    accept?: string;
    maxSizeMB?: number;
}

export default function FileDropzone({
    mode = 'upload',
    onUploaded,
    onFileSelected,
    onClear,
    currentFile = null,
    currentUrl = null,
    disabled = false,
    accept,
    maxSizeMB = 10,
}: FileDropzoneProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFiles = useCallback(async (files: FileList | null) => {
        if (!files?.length || disabled) return;
        const file = files[0];
        if (file.size > maxSizeMB * 1024 * 1024) {
            setError(`File too large (max ${maxSizeMB}MB)`);
            return;
        }
        setError(null);
        if (mode === 'select') {
            onFileSelected?.(file);
            return;
        }
        setUploading(true);
        try {
            const { url } = await uploadFile(file);
            onUploaded?.(url, file);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Upload failed');
        } finally {
            setUploading(false);
        }
    }, [mode, onUploaded, onFileSelected, disabled, maxSizeMB]);

    const onDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) setIsDragging(true);
    }, [disabled]);

    const onDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const onDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (disabled || uploading) return;
        handleFiles(e.dataTransfer.files);
    }, [disabled, uploading, handleFiles]);

    const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        handleFiles(e.target.files);
        e.target.value = '';
    }, [handleFiles]);

    const hasFile = Boolean(currentFile || (currentUrl && mode === 'upload'));

    return (
        <div className="file-dropzone-wrapper">
            <div
                className={`file-dropzone ${isDragging ? 'file-dropzone-dragging' : ''} ${hasFile ? 'file-dropzone-has-file' : ''} ${disabled || uploading ? 'file-dropzone-disabled' : ''}`}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
            >
                <input
                    type="file"
                    className="file-dropzone-input"
                    onChange={onInputChange}
                    disabled={disabled || uploading}
                    accept={accept}
                />
                {uploading ? (
                    <span className="file-dropzone-text">Uploading…</span>
                ) : hasFile ? (
                    <div className="file-dropzone-file">
                        <FileIcon size={20} />
                        <span className="file-dropzone-filename">{currentFile?.name ?? (currentUrl ? 'File attached' : '')}</span>
                        {(onClear || (mode === 'select' && onFileSelected)) && (
                            <button
                                type="button"
                                className="file-dropzone-clear"
                                onClick={() => { if (mode === 'select') onFileSelected?.(null); onClear?.(); }}
                                aria-label="Remove file"
                            >
                                <X size={16} />
                            </button>
                        )}
                    </div>
                ) : (
                    <>
                        <Upload size={28} className="file-dropzone-icon" />
                        <span className="file-dropzone-text">Drag and drop any file here, or click to browse</span>
                        <span className="file-dropzone-hint">Max {maxSizeMB}MB</span>
                    </>
                )}
            </div>
            {error && <p className="file-dropzone-error">{error}</p>}
        </div>
    );
}
