import { useEffect, useMemo, useState } from "react";
import { FileSearch, Pencil, RefreshCcw, Scale, Send, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  deleteDocument,
  listDocuments,
  reExtractDocument,
  releaseDocumentToTaxpayer,
  renameDocument,
  type UploadedDocumentSummary,
} from "@/features/transaction-semantic/api";
import { classifyDocumentExtractedRows } from "@/features/transaction-semantic/classify-document";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";
import { useAuditorTaxpayerId } from "@/hooks/use-auditor-taxpayer-id";

function needsExtraction(document: UploadedDocumentSummary): boolean {
  return (
    document.status === "uploaded" ||
    document.status === "submitted" ||
    document.extracted_row_count === 0
  );
}

function canClassify(document: UploadedDocumentSummary): boolean {
  return document.extracted_row_count > 0;
}

export interface DocumentListPanelProps {
  selectedDocumentId: string | null;
  onSelect: (documentId: string) => void;
  onRenamed?: (documentId: string) => void;
  onExtracted?: (documentId: string) => void;
  onDeleted?: (documentId: string) => void;
  /** Fired after bulk classify finishes (even partially) so monthly rollups can refresh. */
  onClassified?: (documentIds: string[]) => void;
  refreshKey?: number;
  financialProfileId?: string | null;
}

export function DocumentListPanel({
  selectedDocumentId,
  onSelect,
  onRenamed,
  onExtracted,
  onDeleted,
  onClassified,
  refreshKey = 0,
  financialProfileId = null,
}: DocumentListPanelProps) {
  const taxpayerId = useAuditorTaxpayerId();
  const [documents, setDocuments] = useState<UploadedDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);
  const [releasingId, setReleasingId] = useState<string | null>(null);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState<"extract" | "release" | "delete" | "classify" | null>(
    null,
  );
  const [bulkClassifyProgress, setBulkClassifyProgress] = useState<string | null>(null);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  async function loadDocuments(): Promise<void> {
    if (!financialProfileId) {
      setDocuments([]);
      setTotal(0);
      setCheckedIds(new Set());
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await listDocuments(100, 0, financialProfileId);
      setDocuments(response.items);
      setTotal(response.total);
      setCheckedIds((current) => {
        const valid = new Set(response.items.map((item) => item.document_id));
        return new Set([...current].filter((id) => valid.has(id)));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load saved documents.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDocuments();
    setConfirmBulkDelete(false);
  }, [refreshKey, financialProfileId]);

  const checkedDocuments = useMemo(
    () => documents.filter((document) => checkedIds.has(document.document_id)),
    [documents, checkedIds],
  );
  const allChecked = documents.length > 0 && checkedIds.size === documents.length;
  const someChecked = checkedIds.size > 0;
  const extractableChecked = checkedDocuments.filter(needsExtraction);
  const classifiableChecked = checkedDocuments.filter(canClassify);
  const releasableChecked = checkedDocuments.filter(
    (document) => !document.user_visible && document.status === "completed",
  );

  function toggleChecked(documentId: string, checked: boolean): void {
    setCheckedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(documentId);
      else next.delete(documentId);
      return next;
    });
    setConfirmBulkDelete(false);
  }

  function toggleSelectAll(checked: boolean): void {
    if (checked) {
      setCheckedIds(new Set(documents.map((document) => document.document_id)));
    } else {
      setCheckedIds(new Set());
    }
    setConfirmBulkDelete(false);
  }

  function clearChecked(): void {
    setCheckedIds(new Set());
    setConfirmBulkDelete(false);
  }

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

  async function handleDelete(documentId: string): Promise<void> {
    setDeletingId(documentId);
    setError(null);
    try {
      await deleteDocument(documentId);
      setDocuments((current) => current.filter((item) => item.document_id !== documentId));
      setTotal((current) => Math.max(0, current - 1));
      setCheckedIds((current) => {
        const next = new Set(current);
        next.delete(documentId);
        return next;
      });
      setConfirmDeleteId(null);
      onDeleted?.(documentId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove document.");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleBulkExtract(): Promise<void> {
    if (extractableChecked.length === 0) return;
    setBulkBusy("extract");
    setError(null);
    setSuccess(null);
    const failures: string[] = [];
    for (const document of extractableChecked) {
      try {
        const response = await reExtractDocument(document.document_id);
        setDocuments((current) =>
          current.map((item) =>
            item.document_id === document.document_id
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
        onExtracted?.(document.document_id);
      } catch {
        failures.push(document.filename);
      }
    }
    if (failures.length > 0) {
      setError(`Failed to extract: ${failures.join(", ")}`);
    }
    setBulkBusy(null);
  }

  async function handleBulkClassify(): Promise<void> {
    if (classifiableChecked.length === 0) return;
    if (!financialProfileId || !taxpayerId) {
      setError("Select and lock a taxpayer profile before classifying.");
      return;
    }
    setBulkBusy("classify");
    setError(null);
    setSuccess(null);
    setBulkClassifyProgress(null);
    const failures: string[] = [];
    const succeededIds: string[] = [];
    let totalRows = 0;
    for (let i = 0; i < classifiableChecked.length; i += 1) {
      const document = classifiableChecked[i];
      setBulkClassifyProgress(
        `Classifying ${i + 1}/${classifiableChecked.length}: ${document.filename}`,
      );
      try {
        const result = await classifyDocumentExtractedRows({
          documentId: document.document_id,
          bankCode: document.bank_detected,
          financialProfileId,
          taxpayerId,
        });
        if (result.rowCount === 0) {
          failures.push(`${document.filename} (no extracted rows)`);
          continue;
        }
        succeededIds.push(document.document_id);
        totalRows += result.rowCount;
      } catch {
        failures.push(document.filename);
      }
    }
    setBulkClassifyProgress(null);
    if (succeededIds.length > 0) {
      setSuccess(
        `Classified ${succeededIds.length} document(s) · ${totalRows.toLocaleString()} row(s) saved.`,
      );
      onClassified?.(succeededIds);
    }
    if (failures.length > 0) {
      setError(`Failed to classify: ${failures.join(", ")}`);
    }
    setBulkBusy(null);
  }

  async function handleBulkRelease(): Promise<void> {
    if (releasableChecked.length === 0) return;
    setBulkBusy("release");
    setError(null);
    const failures: string[] = [];
    for (const document of releasableChecked) {
      try {
        const response = await releaseDocumentToTaxpayer(document.document_id);
        setDocuments((current) =>
          current.map((item) =>
            item.document_id === document.document_id ? response.document : item,
          ),
        );
      } catch {
        failures.push(document.filename);
      }
    }
    if (failures.length > 0) {
      setError(`Failed to release: ${failures.join(", ")}`);
    }
    setBulkBusy(null);
  }

  async function handleBulkDelete(): Promise<void> {
    if (checkedDocuments.length === 0) return;
    setBulkBusy("delete");
    setError(null);
    const failures: string[] = [];
    const deletedIds: string[] = [];
    for (const document of checkedDocuments) {
      try {
        await deleteDocument(document.document_id);
        deletedIds.push(document.document_id);
        onDeleted?.(document.document_id);
      } catch {
        failures.push(document.filename);
      }
    }
    if (deletedIds.length > 0) {
      const deletedSet = new Set(deletedIds);
      setDocuments((current) => current.filter((item) => !deletedSet.has(item.document_id)));
      setTotal((current) => Math.max(0, current - deletedIds.length));
      setCheckedIds((current) => {
        const next = new Set(current);
        for (const id of deletedIds) next.delete(id);
        return next;
      });
    }
    setConfirmBulkDelete(false);
    if (failures.length > 0) {
      setError(`Failed to remove: ${failures.join(", ")}`);
    }
    setBulkBusy(null);
  }

  const busy = bulkBusy != null || releasingId != null || extractingId != null || deletingId != null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved documents</CardTitle>
        <CardDescription>
          Save statements here or review taxpayer uploads. Check multiple documents for bulk
          actions, or click a name to open one for review.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!financialProfileId ? (
          <ActiveProfileBanner moduleLabel="Document library" />
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {isLoading ? "Loading..." : `${total} saved document(s)`}
            {someChecked ? ` · ${checkedIds.size} selected` : ""}
          </p>
          <Button variant="outline" size="sm" onClick={() => void loadDocuments()} disabled={isLoading || busy}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh list
          </Button>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {success ? <p className="text-sm text-emerald-700 dark:text-emerald-400">{success}</p> : null}
        {bulkClassifyProgress ? (
          <p className="text-sm text-muted-foreground">{bulkClassifyProgress}</p>
        ) : null}

        {documents.length > 0 ? (
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-muted/20 px-3 py-2">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={allChecked}
                onChange={(event) => toggleSelectAll(event.target.checked)}
                disabled={busy || isLoading}
                aria-label="Select all documents"
              />
              <span>{allChecked ? "Clear all" : "Select all"}</span>
            </label>
            {someChecked ? (
              <>
                <Button size="sm" variant="ghost" onClick={clearChecked} disabled={busy}>
                  Clear selection
                </Button>
                {extractableChecked.length > 0 ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void handleBulkExtract()}
                    disabled={busy}
                  >
                    <FileSearch className="mr-2 h-4 w-4" />
                    {bulkBusy === "extract"
                      ? "Extracting…"
                      : `Extract selected (${extractableChecked.length})`}
                  </Button>
                ) : null}
                {classifiableChecked.length > 0 ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void handleBulkClassify()}
                    disabled={busy || !taxpayerId}
                    title={
                      taxpayerId
                        ? "Classify extracted rows for all selected documents and save to the active taxpayer"
                        : "Select and lock a taxpayer profile before classifying"
                    }
                  >
                    <Scale className="mr-2 h-4 w-4" />
                    {bulkBusy === "classify"
                      ? "Classifying…"
                      : `Classify selected (${classifiableChecked.length})`}
                  </Button>
                ) : null}
                {releasableChecked.length > 0 ? (
                  <Button size="sm" onClick={() => void handleBulkRelease()} disabled={busy}>
                    <Send className="mr-2 h-4 w-4" />
                    {bulkBusy === "release"
                      ? "Releasing…"
                      : `Release selected (${releasableChecked.length})`}
                  </Button>
                ) : null}
                {!confirmBulkDelete ? (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setConfirmBulkDelete(true)}
                    disabled={busy}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Remove selected ({checkedIds.size})
                  </Button>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      Remove {checkedIds.size} document(s)?
                    </span>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => void handleBulkDelete()}
                      disabled={busy}
                    >
                      {bulkBusy === "delete" ? "Removing…" : "Confirm remove"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setConfirmBulkDelete(false)}
                      disabled={busy}
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <span className="text-xs text-muted-foreground">
                Use checkboxes to select several documents at once.
              </span>
            )}
          </div>
        ) : null}

        {documents.length === 0 && !isLoading ? (
          <p className="text-sm text-muted-foreground">
            {financialProfileId
              ? "No saved documents for this taxpayer yet. Upload a statement below."
              : "Select a taxpayer in the right panel to view their documents."}
          </p>
        ) : (
          <div className="space-y-2">
            {documents.map((document) => {
              const isActive = selectedDocumentId === document.document_id;
              const isChecked = checkedIds.has(document.document_id);
              const isEditing = editingId === document.document_id;
              const isConfirmingDelete = confirmDeleteId === document.document_id;
              return (
                <div
                  key={document.document_id}
                  className={`rounded-md border p-3 ${
                    isActive
                      ? "border-primary bg-accent/30"
                      : isChecked
                        ? "border-primary/50 bg-muted/30"
                        : "border-border"
                  }`}
                >
                  {isConfirmingDelete ? (
                    <div className="space-y-3">
                      <p className="text-sm">
                        Remove <span className="font-medium">{document.filename}</span>?
                        {document.user_visible ? (
                          <span className="mt-1 block text-xs text-amber-600 dark:text-amber-400">
                            This document was released to the taxpayer. Removing it will hide its
                            transactions from their portal.
                          </span>
                        ) : null}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => void handleDelete(document.document_id)}
                          disabled={deletingId === document.document_id || busy}
                        >
                          {deletingId === document.document_id ? "Removing…" : "Confirm remove"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setConfirmDeleteId(null)}
                          disabled={deletingId === document.document_id || busy}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : isEditing ? (
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
                          disabled={isRenaming || busy}
                        >
                          {isRenaming ? "Saving..." : "Save name"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={cancelRename}
                          disabled={isRenaming || busy}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <Checkbox
                          className="mt-1"
                          checked={isChecked}
                          onChange={(event) =>
                            toggleChecked(document.document_id, event.target.checked)
                          }
                          disabled={busy}
                          aria-label={`Select ${document.filename}`}
                          onClick={(event) => event.stopPropagation()}
                        />
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => onSelect(document.document_id)}
                        >
                          <div className="font-medium break-all">{document.filename}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {document.bank_detected ?? "unknown bank"} ·{" "}
                            {document.extracted_row_count} rows · {document.status}
                            {document.submitted_by === "taxpayer" ? " · taxpayer upload" : ""}
                            {document.user_visible ? " · visible to taxpayer" : " · not released"}
                          </div>
                          <div className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                            {document.document_id}
                          </div>
                        </button>
                      </div>
                      <div className="flex flex-col gap-2">
                        {needsExtraction(document) ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => void handleExtract(document.document_id)}
                            disabled={extractingId === document.document_id || busy}
                          >
                            <FileSearch className="mr-2 h-4 w-4" />
                            {extractingId === document.document_id ? "Extracting…" : "Extract"}
                          </Button>
                        ) : null}
                        {!document.user_visible && document.status === "completed" ? (
                          <Button
                            size="sm"
                            onClick={() => void handleRelease(document.document_id)}
                            disabled={releasingId === document.document_id || busy}
                          >
                            <Send className="mr-2 h-4 w-4" />
                            {releasingId === document.document_id
                              ? "Releasing…"
                              : "Release to taxpayer"}
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => startRename(document)}
                          disabled={busy}
                          aria-label={`Rename ${document.filename}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setConfirmDeleteId(document.document_id)}
                          disabled={busy}
                          aria-label={`Remove ${document.filename}`}
                        >
                          <Trash2 className="h-4 w-4" />
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
