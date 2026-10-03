export function PageLoader({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="page-state" role="status">
      <div aria-hidden="true" className="progress progress--indeterminate">
        <span />
      </div>
      <p>{label}…</p>
    </div>
  );
}
