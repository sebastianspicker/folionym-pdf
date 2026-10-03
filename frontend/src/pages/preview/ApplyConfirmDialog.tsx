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
      title={`Write ${selectedCount} ${nameLabel}?`}
    >
      <div className="apply-confirmation">
        <p>
          {selectedCount} {selectedCount === 1 ? "file" : "files"} in <code className="filename">{compactPath(source)}</code>{" "}
          will get the exact {nameLabel} you reviewed. If a file changed since Preview, or its new name is now taken,
          that file is left alone and reported.
        </p>
        <dl className="confirm-summary">
          <div>
            <dt>Names</dt>
            <dd>Exactly as reviewed, not recomputed</dd>
          </div>
          <div>
            <dt>Marked Review</dt>
            <dd className={reviewCount ? "is-attention" : undefined}>
              {reviewCount} in this preview; only ticked ones are written
            </dd>
          </div>
          <div>
            <dt>Left alone</dt>
            <dd>{skippedFailedCount} skipped or failed, plus anything unticked</dd>
          </div>
          <div>
            <dt>Model setting</dt>
            <dd>{localOnly ? "Loopback endpoint, or no model" : "External endpoint: document text may have left this computer"}</dd>
          </div>
        </dl>
      </div>
    </Modal>
  );
}
