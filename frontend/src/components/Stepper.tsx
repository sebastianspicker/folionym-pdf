const STAGES = [
  { id: 1 as const, key: "source", label: "Source" },
  { id: 2 as const, key: "preview", label: "Preview" },
  { id: 3 as const, key: "apply", label: "Apply" },
];

export function Stepper({ active }: { active: 1 | 2 | 3 }) {
  return (
    <nav aria-label="Rename stages" className="stepper">
      <ol>
        {STAGES.map((stage) => {
          const done = active > stage.id;
          const current = active === stage.id;
          const className = [
            "stage",
            done ? "stage--done" : "",
            current ? "stage--current" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <li
              aria-current={current ? "step" : undefined}
              className={className}
              key={stage.id}
            >
              <span className="stage-hit" data-stage={stage.key}>
                <span aria-hidden="true" className="stage-node">
                  {done ? "✓" : stage.id}
                </span>
                <span className="stage-label">
                  <strong>{stage.label}</strong>
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
