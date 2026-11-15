export function orderResourceIds(ids: string[], resources: { id: string }[]): string[] {
  const positions = new Map(resources.map((resource, index) => [resource.id, index]));
  return ids.toSorted(
    (left, right) =>
      (positions.get(left) ?? positions.size) - (positions.get(right) ?? positions.size),
  );
}
