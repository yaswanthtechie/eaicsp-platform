export function filterData<T extends Record<string, unknown>>(
  data: T[],
  filters: Partial<Record<keyof T, string>>
): T[] {
  return data.filter((row) => {
    return Object.entries(filters).every(([key, value]) => {
      if (!value) {
        return true;
      }

      const cellValue = row[key as keyof T];

      return String(cellValue)
        .toLowerCase()
        .includes(value.toLowerCase());
    });
  });
}