import { Button } from "../../components";

type PreviewFooterProps = {
  selectedCount: number;
  onBack: () => void;
  onOpenConfirm: () => void;
};

const modifier =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl ";

export function PreviewFooter({ selectedCount, onBack, onOpenConfirm }: PreviewFooterProps) {
  const nameLabel = selectedCount === 1 ? "name" : "names";

  return (
    <>
      <div className="consequence-copy" aria-live="polite">
        <span className="consequence-count" key={selectedCount}>{selectedCount}</span>
        <div>
          <strong>
            {nameLabel} ticked to write
          </strong>
          <p>Apply re-checks each file and target first. Unticked files stay exactly as they are.</p>
        </div>
      </div>
      <p className="consequence-keys">
        <kbd>/</kbd> find <kbd>{modifier}A</kbd> select page <kbd>{modifier}↵</kbd> apply
      </p>
      <div className="consequence-actions">
        <Button onClick={onBack} type="button">Back to Source</Button>
        <Button disabled={selectedCount === 0} onClick={onOpenConfirm} type="button" variant="primary">
          Apply {selectedCount} {nameLabel}
        </Button>
      </div>
    </>
  );
}
