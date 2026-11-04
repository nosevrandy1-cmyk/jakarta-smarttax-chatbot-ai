/** Rendering only: these settings never truncate stored history or model context. */
export const CHAT_RENDERING = {
  threshold: 40,
  overscan: 6,
  estimatedMessageHeight: 180,
  messageGap: 24,
} as const;

export function shouldVirtualizeChat(count:number):boolean {
  return count > CHAT_RENDERING.threshold;
}

/** Keep original indices for edit/retry actions and stable IDs for measured rows. */
export function selectVirtualMessages<T>(messages:readonly T[],items:readonly {index:number;start:number}[]) {
  return items.filter(item=>item.index>=0&&item.index<messages.length)
    .map(item=>({index:item.index,offset:item.start,message:messages[item.index]}));
}
