type RoomResource = "channels" | "channels-order" | "selected-channel";
type ChannelResource =
  | "draft"
  | "publication"
  | "skills"
  | "topics-order"
  | "members-order"
  | "channel-creation"
  | "seen-seq";

export function appCacheKey(
  resource: "rooms-order" | "panels" | "message-dots-initialized",
): string {
  return `conflua:app:${resource}`;
}

export function roomCacheKey(roomId: string, resource?: RoomResource): string {
  const scope = `conflua:room:${encodeURIComponent(roomId)}`;
  return resource ? `${scope}:${resource}` : scope;
}

export function channelResourceKey(scope: string, resource: ChannelResource): string {
  return `${scope}:${resource}`;
}

export function channelCacheKey(
  roomId: string,
  channelId: string,
  resource?: ChannelResource,
): string {
  const scope = `${roomCacheKey(roomId)}:channel:${encodeURIComponent(channelId)}`;
  return resource ? channelResourceKey(scope, resource) : scope;
}
