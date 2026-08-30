import { useEffect, useState } from "react";
import { FileSearch, Pencil, RefreshCcw, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  listDocuments,
  reExtractDocument,
  releaseDocumentToTaxpayer,
  renameDocument,
  type UploadedDocumentSummary,
} from "@/features/transaction-semantic/api";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";

function needsExtraction(document: UploadedDocumentSummary): boolean {
  return (
    document.status === "uploaded" ||
    document.status === "submitted" ||
    document.extracted_row_count === 0
  );
}

export interface DocumentListPanelProps {
  selectedDocumentId: string | null;
  onSelect: (documentId: string) => void;
  onRenamed?: (documentId: string) => void;
  onExtracted?: (documentId: string) => void;
  refreshKey?: number;
  financialProfileId?: string | null;
}

export function DocumentListPanel({
  selectedDocumentId,
  onSelect,
  onRenamed,
  onExtracted,
  refreshKey = 0,
  financialProfileId = null,
}: DocumentListPanelProps) {
  const [documents, setDocuments] = useState<UploadedDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);
  const [releasingId, setReleasingId] = useState<string | null>(null);
  const [extractingId, setExtractingId] = useState<string | null>(null);

  async function loadDocuments(): Promise<void> {
    if (!financialProfileId) {
      setDocuments([]);
      setTotal(0);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await listDocuments(100, 0, financialProfileId);
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
  }, [refreshKey, financialProfileId]);

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

  async function handleRelease(documentId: string): Promise<void> {
    setReleasingId(documentId);
    setError(null);
    try {
      const response = await releaseDocumentToTaxpayer(documentId);
      setDocuments((current) =>
        current.map((item) => (item.document_id === documentId ? response.document : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to release document.");
    } finally {
      setReleasingId(null);
    }
  }

  async function handleExtract(documentId: string): Promise<void> {
    setExtractingId(documentId);
    setError(null);
    try {
      const response = await reExtractDocument(documentId);
      setDocuments((current) =>
        current.map((item) =>
          item.document_id === documentId
            ? {
                ...item,
                status: response.status,
                bank_detected: response.bank_detected,
                selected_parser: response.selected_parser,
                extracted_row_count: response.extracted_row_count,
              }
            : item,
        ),
      );
      onExtracted?.(documentId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to extract document.");
    } finally {
      setExtractingId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved documents</CardTitle>
        <CardDescription>
          Save statements here or review taxpayer uploads. Select a document, then Extract when ready.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!financialProfileId ? (
          <ActiveProfileBanner moduleLabel="Document library" />
        ) : null}
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
            {financialProfileId
              ? "No saved documents for this taxpayer yet. Upload a statement below."
              : "Select a taxpayer in the right panel to view their documents."}
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
                          {document.submitted_by === "taxpayer" ? " · taxpayer upload" : ""}
                          {document.user_visible ? " · visible to taxpayer" : " · not released"}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                          {document.document_id}
                        </div>
                      </button>
                      <div className="flex flex-col gap-2">
                        {needsExtraction(document) ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => void handleExtract(document.document_id)}
                            disabled={extractingId === document.document_id}
                          >
                            <FileSearch className="mr-2 h-4 w-4" />
                            {extractingId === document.document_id ? "Extracting…" : "Extract"}
                          </Button>
                        ) : null}
                        {!document.user_visible && document.status === "completed" ? (
                          <Button
                            size="sm"
                            onClick={() => void handleRelease(document.document_id)}
                            disabled={releasingId === document.document_id}
                          >
                            <Send className="mr-2 h-4 w-4" />
                            {releasingId === document.document_id ? "Releasing…" : "Release to taxpayer"}
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => startRename(document)}
                          aria-label={`Rename ${document.filename}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </div>
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
