// Keep stable row IDs scoped to the estimate. Never choose by work name.
export function createJournalLineLinks() {
  const aliases = new Map();
  const positions = new Map();
  const aliasKey = (estimateId, value) => JSON.stringify([String(estimateId), String(value)]);
  return {
    add(estimateId, sectionIndex, itemIndex, item) {
      const position = `${estimateId}:${sectionIndex}:${itemIndex}`;
      positions.set(position, String(estimateId));
      for (const value of [position, item.id, item.workKey]) {
        if (value === null || value === undefined || String(value) === '') continue;
        const key = aliasKey(estimateId, value);
        aliases.set(key, aliases.has(key) && aliases.get(key) !== position ? null : position);
      }
      return position;
    },
    resolve(entry) {
      const value = String(entry.estimateItemKey || '');
      const id = entry.estimateId;
      const scoped = id !== undefined && id !== null && id !== '';
      if (scoped) return aliases.get(aliasKey(id, value)) || null;
      // Historical positional keys already contain their estimate scope.
      const estimateId = positions.get(value);
      return estimateId ? aliases.get(aliasKey(estimateId, value)) || null : null;
    },
  };
}
