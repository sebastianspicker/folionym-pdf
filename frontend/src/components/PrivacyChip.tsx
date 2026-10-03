export function PrivacyChip({ external }: { external: boolean }) {
  const detail = external
    ? "Document text may leave this machine for the configured model endpoint."
    : "Rules and heuristics only, or a model at a loopback address on this computer.";
  return (
    <div
      className={`privacy-chip ${external ? "privacy-chip--external" : "privacy-chip--local"}`}
      role="status"
      title={detail}
    >
      <span aria-hidden="true" className="privacy-mark" />
      <span className="privacy-label">{external ? "External model" : "Local only"}</span>
      <span className="visually-hidden">{detail}</span>
    </div>
  );
}
