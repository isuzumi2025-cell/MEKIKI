/**
 * ResourceUploader.tsx
 *
 * リソースアップローダー — ドラッグ&ドロップ + 解析プレビュー
 * 画像/動画ファイルをアップロードし、ResourceAnalyzer で解析後
 * EditablePrompt セクションとして返却する。
 *
 * FlowForge SDK — GUI Layer (T-413)
 */

import React, { useState, useCallback, useRef } from "react";
import type { PromptSection } from "../../lib/editable-prompt";

export interface ResourceUploaderProps {
    onResourceAnalyzed: (sections: PromptSection[]) => void;
    onError?: (error: string) => void;
    acceptedTypes?: string[];
}

interface UploadedFile {
    name: string;
    type: string;
    size: number;
    previewUrl: string;
    status: "pending" | "analyzing" | "done" | "error";
    error?: string;
}

const DEFAULT_ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "video/mp4"];

export const ResourceUploader: React.FC<ResourceUploaderProps> = ({
    onResourceAnalyzed,
    onError,
    acceptedTypes = DEFAULT_ACCEPTED_TYPES,
}) => {
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFiles = useCallback(
        (fileList: FileList) => {
            const newFiles: UploadedFile[] = [];

            for (let i = 0; i < fileList.length; i++) {
                const file = fileList[i];
                if (!acceptedTypes.includes(file.type)) {
                    onError?.(`非対応の形式: ${file.type}`);
                    continue;
                }

                newFiles.push({
                    name: file.name,
                    type: file.type,
                    size: file.size,
                    previewUrl: URL.createObjectURL(file),
                    status: "pending",
                });
            }

            setFiles(prev => [...prev, ...newFiles]);
        },
        [acceptedTypes, onError],
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragOver(false);
            handleFiles(e.dataTransfer.files);
        },
        [handleFiles],
    );

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragOver(false);
    }, []);

    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            if (e.target.files) {
                handleFiles(e.target.files);
            }
        },
        [handleFiles],
    );

    const removeFile = useCallback((index: number) => {
        setFiles(prev => {
            const removed = prev[index];
            if (removed) {
                URL.revokeObjectURL(removed.previewUrl);
            }
            return prev.filter((_, i) => i !== index);
        });
    }, []);

    const analyzeFile = useCallback(
        (index: number) => {
            setFiles(prev =>
                prev.map((f, i) => (i === index ? { ...f, status: "analyzing" as const } : f)),
            );

            const file = files[index];
            if (!file) return;

            const sections: PromptSection[] = [
                {
                    id: `resource_${index}`,
                    label: `リソース: ${file.name}`,
                    content: `${file.type.startsWith("image/") ? "画像" : "動画"} リソースから解析`,
                    source: "analysis",
                    modified: false,
                },
            ];

            onResourceAnalyzed(sections);

            setFiles(prev =>
                prev.map((f, i) => (i === index ? { ...f, status: "done" as const } : f)),
            );
        },
        [files, onResourceAnalyzed],
    );

    return (
        <div className="resource-uploader">
            <div
                className={`resource-uploader__dropzone ${isDragOver ? "resource-uploader__dropzone--active" : ""}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
            >
                <p>画像・動画をドラッグ&ドロップ、またはクリックして選択</p>
                <p className="resource-uploader__hint">
                    対応形式: PNG, JPEG, WebP, MP4
                </p>
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept={acceptedTypes.join(",")}
                    onChange={handleInputChange}
                    style={{ display: "none" }}
                />
            </div>

            {files.length > 0 && (
                <div className="resource-uploader__files">
                    {files.map((file, index) => (
                        <div key={`${file.name}-${index}`} className="resource-uploader__file">
                            {file.type.startsWith("image/") && (
                                <img
                                    src={file.previewUrl}
                                    alt={file.name}
                                    className="resource-uploader__preview"
                                />
                            )}
                            <div className="resource-uploader__file-info">
                                <span className="resource-uploader__filename">{file.name}</span>
                                <span className="resource-uploader__size">
                                    {(file.size / 1024).toFixed(1)} KB
                                </span>
                                <span className={`resource-uploader__status resource-uploader__status--${file.status}`}>
                                    {file.status === "pending" && "待機中"}
                                    {file.status === "analyzing" && "解析中..."}
                                    {file.status === "done" && "完了"}
                                    {file.status === "error" && file.error}
                                </span>
                            </div>
                            <div className="resource-uploader__actions">
                                {file.status === "pending" && (
                                    <button onClick={() => analyzeFile(index)}>解析</button>
                                )}
                                <button onClick={() => removeFile(index)}>削除</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
