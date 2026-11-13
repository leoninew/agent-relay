import type { Delivery } from "@/services/roomApi";

export function deliveryStage(
  deliveries: Delivery[],
): "received" | "receiving" | "sending" | "failed" | "unknown" | undefined {
  const remaining = deliveries.filter((delivery) => !delivery.deletedAt);
  if (!remaining.length) return undefined;
  if (remaining.some((delivery) => delivery.status === "rejected")) return "failed";
  if (remaining.some((delivery) => delivery.status === "unknown")) return "unknown";
  if (remaining.every((delivery) => delivery.status === "received")) return "received";
  if (remaining.every((delivery) => delivery.status === "queued" || delivery.status === "received"))
    return "receiving";
  return "sending";
}
