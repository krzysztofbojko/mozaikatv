export type SourceStatus = 'online' | 'delayed' | 'offline' | 'disabled';

export interface TileSnapshot {
  source_id: string;
  title: string;
  batch_id: string;
  frame_url: string;
  captured_at: string;
  position_seconds: number;
  status: SourceStatus;
  error: string | null;
}

export interface MosaicState {
  version: number;
  batch_id: string;
  published_at: string;
  next_refresh_seconds: number | null;
  tiles: TileSnapshot[];
}

export interface StreamConfig {
  slot: number;
  source_type: 'none' | 'local' | 'youtube';
  filename: string;
  url: string;
  title: string;
}

export interface AdminConfig {
  refresh_min_seconds: number;
  refresh_max_seconds: number;
  frame_width: number;
  frame_height: number;
  webp_quality: number;
  streams: StreamConfig[];
}

export interface AdminPayload {
  config: AdminConfig;
  available_videos: string[];
}
