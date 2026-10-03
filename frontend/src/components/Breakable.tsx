import { Fragment } from "react";

/**
 * Renders a path or filename with optional line-break points after `/`, `_`,
 * and `.` so long names wrap at their own separators instead of mid-word.
 * Hyphens already allow a break. The final extension never wraps on its own.
 */
export function Breakable({ text }: { text: string }) {
  const parts = text.split(/(?<=[/_]|\.(?=[^.]*\.))/);
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          {index > 0 ? <wbr /> : null}
          {part}
        </Fragment>
      ))}
    </>
  );
}
