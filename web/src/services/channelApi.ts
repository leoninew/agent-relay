import { apiClient } from "@/services/api";
import type { RoomSnapshot } from "@/services/roomApi";

export type ChannelWorkspaceKind = "existing" | "worktree";

export type Channel = {
  id: string;
  roomId: string;
  name: string;
  description: string;
  workingPath: string;
  workingPathKey?: string | null;
  isDefault: boolean;
  workspaceKind: ChannelWorkspaceKind;
  branch?: string | null;
  baseCommit?: string | null;
  createdAt: string | null;
  archivedAt?: string | null;
};

export type CreateChannel = {
  name: string;
  description: string;
  channelId?: string;
  useWorktree: boolean;
};

export type ChannelSnapshot = RoomSnapshot & {
  channelId: string;
  workingPath: string;
};

function channelBase(roomId: string): string {
  return `/api/room/${encodeURIComponent(roomId)}/channel`;
}

function channelPath(roomId: string, channelId: string): string {
  return `${channelBase(roomId)}/${encodeURIComponent(channelId)}`;
}

export async function fetchChannels(roomId: string, signal?: AbortSignal): Promise<Channel[]> {
  const { data } = await apiClient.get<Channel[]>(channelBase(roomId), { signal });
  return data;
}

export async function createChannel(roomId: string, request: CreateChannel): Promise<Channel> {
  const { data } = await apiClient.post<Channel>(channelBase(roomId), request);
  return data;
}

export async function fetchChannel(
  roomId: string,
  channelId: string,
  signal?: AbortSignal,
): Promise<Channel> {
  const { data } = await apiClient.get<Channel>(channelPath(roomId, channelId), { signal });
  return data;
}

export async function deleteChannel(roomId: string, channelId: string): Promise<void> {
  await apiClient.delete(channelPath(roomId, channelId));
}
