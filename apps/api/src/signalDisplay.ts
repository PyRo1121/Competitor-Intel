export function signalLabelFromRow(
  signalType: string,
  dataJson: string | null | undefined,
): string {
  if (!dataJson) {
    return signalType;
  }
  try {
    const data = JSON.parse(dataJson) as Record<string, unknown>;
    const kind =
      (typeof data.kind === "string" && data.kind) ||
      (typeof data.category === "string" && data.category) ||
      (typeof data.launch_type === "string" && data.launch_type) ||
      (typeof data.story_type === "string" && data.story_type);
    if (kind) {
      return kind;
    }
  } catch {
    return signalType;
  }
  if (/^[a-f0-9]{16}$/i.test(signalType)) {
    return "signal";
  }
  return signalType;
}
