import { useEffect, useState } from "react";
import { Pencil, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  listDocuments,
  renameDocument,
  type UploadedDocumentSummary,
} from "@/features/transaction-semantic/api";

export interface DocumentListPanelProps {
  selectedDocumentId: string | null;
  onSelect: (documentId: string) => void;
  onRenamed?: (documentId: string) => void;
  refreshKey?: number;
}

export function DocumentListPanel({
  selectedDocumentId,
  onSelect,
  onRenamed,
  refreshKey = 0,
}: DocumentListPanelProps) {
  const [documents, setDocuments] = useState<UploadedDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);

  async function loadDocuments(): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listDocuments(100, 0);
      setDocuments(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load saved documents.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, [refreshKey]);

  function startRename(document: UploadedDocumentSummary): void {
    setEditingId(document.document_id);
    setDraftName(document.filename);
    setError(null);
  }

  function cancelRename(): void {
    setEditingId(null);
    setDraftName("");
  }

  async function saveRename(documentId: string): Promise<void> {
    const nextName = draftName.trim();
    if (!nextName) {
      setError("Document name cannot be empty.");
      return;
    }
    setIsRenaming(true);
    setError(null);
    try {
      const response = await renameDocument(documentId, nextName);
      setDocuments((current) =>
        current.map((item) =>
          item.document_id === documentId ? response.document : item,
        ),
      );
      setEditingId(null);
      setDraftName("");
      onRenamed?.(documentId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename document.");
    } finally {
      setIsRenaming(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved documents</CardTitle>
        <CardDescription>
          Uploads are stored in the database with extracted rows linked by document ID.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {isLoading ? "Loading..." : `${total} saved document(s)`}
          </p>
          <Button variant="outline" size="sm" onClick={() => void loadDocuments()} disabled={isLoading}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh list
          </Button>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {documents.length === 0 && !isLoading ? (
          <p className="text-sm text-muted-foreground">
            No saved documents yet. Upload a statement to create one.
          </p>
        ) : (
          <div className="space-y-2">
            {documents.map((document) => {
              const isSelected = selectedDocumentId === document.document_id;
              const isEditing = editingId === document.document_id;
              return (
                <div
                  key={document.document_id}
                  className={`rounded-md border p-3 ${isSelected ? "border-primary bg-accent/30" : "border-border"}`}
                >
                  {isEditing ? (
                    <div className="space-y-2">
                      <Label htmlFor={`rename-${document.document_id}`}>Document name</Label>
                      <Input
                        id={`rename-${document.document_id}`}
                        value={draftName}
                        onChange={(event) => setDraftName(event.target.value)}
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          onClick={() => void saveRename(document.document_id)}
                          disabled={isRenaming}
                        >
                          {isRenaming ? "Saving..." : "Save name"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={cancelRename} disabled={isRenaming}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left"
                        onClick={() => onSelect(document.document_id)}
                      >
                        <div className="font-medium break-all">{document.filename}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {document.bank_detected ?? "unknown bank"} · {document.extracted_row_count} rows ·{" "}
                          {document.status}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                          {document.document_id}
                        </div>
                      </button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startRename(document)}
                        aria-label={`Rename ${document.filename}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
