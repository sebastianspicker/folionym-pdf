import { Button, Modal, compactPath } from "../../components";

type ApplyConfirmDialogProps = {
  open: boolean;
  selectedCount: number;
  reviewCount: number;
  skippedFailedCount: number;
  source: string;
  localOnly: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

export function ApplyConfirmDialog({
  open,
  selectedCount,
  reviewCount,
  skippedFailedCount,
  source,
  localOnly,
  onClose,
  onConfirm,
}: ApplyConfirmDialogProps) {
  const nameLabel = selectedCount === 1 ? "name" : "names";

  return (
    <Modal
      footer={
        <>
          <Button onClick={onClose}>Keep reviewing</Button>
          <Button onClick={onConfirm} variant="primary">
            Apply {selectedCount} {nameLabel}
          </Button>
        </>
      }
      onClose={onClose}
      open={open}
      title={`Write ${selectedCount} selected ${nameLabel}?`}
    >
      <div className="apply-confirmation">
        <p>
          <strong>{selectedCount} files</strong> in{" "}
          <code>{compactPath(source)}</code> will be renamed to their exact
          reviewed targets. Changed sources and new collisions fail safely.
        </p>
        <dl className="confirm-summary">
          <div>
            <dt>Plan</dt>
            <dd>Exact targets · no recompute</dd>
          </div>
          <div>
            <dt>Review</dt>
            <dd>{reviewCount} marked for attention</dd>
          </div>
          <div>
            <dt>Untouched</dt>
            <dd>{skippedFailedCount} skipped or failed</dd>
          </div>
          <div>
            <dt>Privacy</dt>
            <dd>
              {localOnly ? "Local only" : "External model used during Preview"}
            </dd>
          </div>
        </dl>
      </div>
    </Modal>
  );
}
