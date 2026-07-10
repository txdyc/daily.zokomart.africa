export function splitParagraphs(text: string): string[] {
  return text
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

export function joinParagraphs(paragraphs: string[] | null | undefined): string {
  return (paragraphs ?? []).join("\n\n");
}
