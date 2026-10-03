import type { Settings } from "../types";
import { Breakable } from "./Breakable";

type Part = { field: string; words: string[] };

// Illustrative words only. The real values come from each document at Preview.
const EXAMPLE = {
  date: "20240115",
  category: ["invoice"],
  keywords: ["acme", "web", "hosting"],
  summary: ["annual", "plan"],
};

function words(value: string): string[] {
  return value
    .trim()
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean)
    .map((word) => word.toLowerCase());
}

function exampleParts(settings: Settings): Part[] {
  const parts: Part[] = [{ field: "date", words: [EXAMPLE.date] }];
  // The backend omits a project or version literally named "default".
  const project = settings.project.trim().toLowerCase() === "default" ? [] : words(settings.project);
  const version = settings.version.trim().toLowerCase() === "default" ? [] : words(settings.version);
  if (project.length) parts.push({ field: "project", words: project });
  parts.push({ field: "category", words: EXAMPLE.category });
  parts.push({ field: "keywords", words: EXAMPLE.keywords });
  parts.push({ field: "summary", words: EXAMPLE.summary });
  if (version.length) parts.push({ field: "version", words: version });
  return parts;
}

function joinWords(list: string[], namingCase: Settings["case"], leading: boolean): string {
  if (namingCase === "camelCase") {
    return list
      .map((word, index) => (leading && index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1)))
      .join("");
  }
  return list.join(namingCase === "snakeCase" ? "_" : "-");
}

/**
 * Shows the shape of a default Folionym filename with the current case,
 * project, and version, each segment labelled. A custom template replaces the
 * default structure, so it is shown verbatim instead.
 */
export function NameAnatomy({ settings }: { settings: Settings }) {
  const template = settings.template.trim();
  if (template) {
    return (
      <figure className="anatomy anatomy--template">
        <code className="anatomy-name filename"><Breakable text={`${template}.pdf`} /></code>
        <figcaption>Custom template. Fields in braces are filled from each document.</figcaption>
      </figure>
    );
  }
  const separator = settings.case === "camelCase" ? "" : settings.case === "snakeCase" ? "_" : "-";
  const parts = exampleParts(settings);
  return (
    <figure className="anatomy" data-case={settings.case}>
      <div aria-hidden="true" className="anatomy-name">
        {parts.map((part, index) => (
          <span className="anatomy-part" data-field={part.field} key={part.field}>
            <span className="anatomy-text">
              {index > 0 && separator ? <span className="anatomy-sep">{separator}</span> : null}
              {joinWords(part.words, settings.case, index === 0)}
            </span>
            <span className="anatomy-field">{part.field}</span>
          </span>
        ))}
        <span className="anatomy-part anatomy-part--ext">
          <span className="anatomy-text">.pdf</span>
        </span>
      </div>
      <figcaption>
        <span className="visually-hidden">
          Example filename:{" "}
          {parts.map((part, index) => `${index > 0 ? separator : ""}${joinWords(part.words, settings.case, index === 0)}`).join("")}
          .pdf, built from {parts.map((part) => part.field).join(", ")}.{" "}
        </span>
        Example only. Each document supplies its own date and words.
      </figcaption>
    </figure>
  );
}
