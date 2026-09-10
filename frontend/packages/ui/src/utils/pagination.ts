export function paginateData<T>(
  data: T[],
  currentPage: number,
  pageSize: number
): T[] {
  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;

  return data.slice(start, end);
}

export function getTotalPages(
  totalItems: number,
  pageSize: number
): number {
  return Math.ceil(totalItems / pageSize);
}