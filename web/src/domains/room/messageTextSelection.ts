export function constrainMessageClickSelection(event: MouseEvent): void {
  if (event.detail !== 2 && event.detail !== 3) {
    return;
  }
  const content = event.currentTarget;
  const target = event.target;
  if (!(content instanceof HTMLElement) || !(target instanceof Element)) {
    return;
  }
  const selection = content.ownerDocument.getSelection();
  if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) {
    return;
  }

  const block = target.closest("p, pre, li, th, td, h1, h2, h3, h4, h5, h6");
  const root = block && content.contains(block) ? block : content;
  const range = selection.getRangeAt(0);
  const walker = content.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let first: Text | undefined;
  let last: Text | undefined;
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    if (
      !range.intersectsNode(node) ||
      node.parentElement?.closest("[hidden], .message-image-frame")
    ) {
      continue;
    }
    const from = range.startContainer === node ? range.startOffset : 0;
    const to = range.endContainer === node ? range.endOffset : node.length;
    if (to <= from) {
      continue;
    }
    first ??= node;
    last = node;
  }
  if (!first || !last || (first === range.startContainer && last === range.endContainer)) {
    return;
  }
  const clipped = range.cloneRange();
  if (first !== range.startContainer) {
    clipped.setStart(first, 0);
  }
  if (last !== range.endContainer) {
    clipped.setEnd(last, last.length);
  }
  selection.removeAllRanges();
  selection.addRange(clipped);
}
