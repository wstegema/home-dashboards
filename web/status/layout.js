// Which layout to use, and which items are on screen when there are too many.

export const PAGE_SIZE = 6;
export const ROTATE_MS = 8000;

// Layout names match data-layout values in layouts.css.
export function pickLayout(count) {
  if (count === 0) return "idle";
  if (count === 1) return "one";
  if (count === 2) return "two";
  if (count <= 4) return "grid4";
  return "grid6";
}

export const pageCount = (items) => Math.max(1, Math.ceil(items.length / PAGE_SIZE));

export function itemsOnPage(items, page) {
  const p = page % pageCount(items);
  return items.slice(p * PAGE_SIZE, (p + 1) * PAGE_SIZE);
}
