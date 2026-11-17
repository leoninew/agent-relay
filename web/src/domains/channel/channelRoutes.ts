import { channelCacheKey } from "@/services/cacheKeys";

export const DEFAULT_CHANNEL_ID = "channel-default";

export function channelKey(roomId: string, channelId: string): string {
  return channelCacheKey(roomId, channelId);
}

export function draftScope(roomId: string, channelId: string): string {
  return channelKey(roomId, channelId);
}

export function snapshotScope(roomId: string, channelId: string): string {
  return channelKey(roomId, channelId);
}

export function roomResourcePath(roomId: string, channelId: string, suffix = ""): string {
  const room = `/api/room/${encodeURIComponent(roomId)}`;
  const channel = `${room}/channel/${encodeURIComponent(channelId)}`;
  return `${channel}${suffix || "/snapshot"}`;
}
