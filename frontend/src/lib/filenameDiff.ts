export type FilenameSegment = {
  text: string;
  changed: boolean;
};

type LcsCell = "keep" | "remove" | "add";

const TOKEN_PATTERN = /(\p{L}[\p{L}\p{N}]*|\p{N}+|[^\p{L}\p{N}]+)/gu;

function tokenizeFilename(name: string): string[] {
  return name.match(TOKEN_PATTERN) ?? [];
}

/**
 * Marks only the proposed tokens that do not belong to a longest common
 * subsequence. Separators are tokens too, so punctuation remains faithfully
 * aligned rather than being painted by a lossy whitespace split.
 */
export function changedFilenameSegments(
  currentName: string,
  proposedName: string,
): FilenameSegment[] {
  if (!proposedName) return [];
  const current = tokenizeFilename(currentName);
  const proposed = tokenizeFilename(proposedName);
  if (currentName === proposedName)
    return [{ text: proposedName, changed: false }];

  const scores = Array.from(
    { length: current.length + 1 },
    () => new Uint16Array(proposed.length + 1),
  );
  for (
    let sourceIndex = current.length - 1;
    sourceIndex >= 0;
    sourceIndex -= 1
  ) {
    for (
      let proposedIndex = proposed.length - 1;
      proposedIndex >= 0;
      proposedIndex -= 1
    ) {
      scores[sourceIndex][proposedIndex] =
        current[sourceIndex] === proposed[proposedIndex]
          ? scores[sourceIndex + 1][proposedIndex + 1] + 1
          : Math.max(
              scores[sourceIndex + 1][proposedIndex],
              scores[sourceIndex][proposedIndex + 1],
            );
    }
  }

  const unchanged = new Set<number>();
  let sourceIndex = 0;
  let proposedIndex = 0;
  while (sourceIndex < current.length && proposedIndex < proposed.length) {
    const direction: LcsCell =
      current[sourceIndex] === proposed[proposedIndex]
        ? "keep"
        : scores[sourceIndex + 1][proposedIndex] >=
            scores[sourceIndex][proposedIndex + 1]
          ? "remove"
          : "add";
    if (direction === "keep") {
      unchanged.add(proposedIndex);
      sourceIndex += 1;
      proposedIndex += 1;
    } else if (direction === "remove") {
      sourceIndex += 1;
    } else {
      proposedIndex += 1;
    }
  }

  return proposed.reduce<FilenameSegment[]>((segments, text, index) => {
    const changed = !unchanged.has(index);
    const previous = segments.at(-1);
    if (previous && previous.changed === changed) previous.text += text;
    else segments.push({ text, changed });
    return segments;
  }, []);
}
