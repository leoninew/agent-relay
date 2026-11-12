import type { Delivery } from "@/services/roomApi";

export function deliveryStage(
  deliveries: Delivery[],
): "已接收" | "接收中" | "发送中" | "发送失败" | "发送待确认" | undefined {
  const remaining = deliveries.filter((delivery) => !delivery.deletedAt);
  if (!remaining.length) return undefined;
  if (remaining.some((delivery) => delivery.status === "rejected")) return "发送失败";
  if (remaining.some((delivery) => delivery.status === "unknown")) return "发送待确认";
  if (remaining.every((delivery) => delivery.status === "received")) return "已接收";
  if (remaining.every((delivery) => delivery.status === "queued" || delivery.status === "received"))
    return "接收中";
  return "发送中";
}
