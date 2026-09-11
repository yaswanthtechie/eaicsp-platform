export type SortDirection = "asc" | "desc";

export function sortData<T extends Record<string, unknown>>(
  data: T[],
  key: keyof T,
  direction: SortDirection
): T[] {
  return [...data].sort((a, b) => {
    const first = a[key];
    const second = b[key];

    if (first == null) return 1;
    if (second == null) return -1;

    if (typeof first === "number" && typeof second === "number") {
      return direction === "asc"
        ? first - second
        : second - first;
    }

    const firstValue = String(first).toLowerCase();
    const secondValue = String(second).toLowerCase();

    if (direction === "asc") {
      return firstValue.localeCompare(secondValue);
    }

    return secondValue.localeCompare(firstValue);
  });
}