import type { Delivery } from "@/services/roomApi";

export function deliveryStage(deliveries: Delivery[]): "已接收" | "接收中" | "入队中" | undefined {
  const remaining = deliveries.filter((delivery) => !delivery.deletedAt);
  if (!remaining.length) return undefined;
  if (remaining.every((delivery) => delivery.status === "received")) return "已接收";
  if (remaining.every((delivery) => delivery.status === "queued" || delivery.status === "received"))
    return "接收中";
  return "入队中";
}
