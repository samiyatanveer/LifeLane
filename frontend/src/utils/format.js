/**
 * Formatting utilities for LifeLane frontend
 */

/**
 * Format an ISO timestamp to a human-readable string
 */
export function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    return new Intl.DateTimeFormat('en-PK', {
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date(ts));
  } catch {
    return ts;
  }
}

/**
 * Format timestamp as relative time (e.g. "2 min ago")
 */
export function formatRelativeTime(ts) {
  if (!ts) return '—';
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 5) return 'just now';
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return formatTimestamp(ts);
  } catch {
    return ts;
  }
}

/**
 * Format a confidence value (0–1) to a percentage string
 */
export function formatConfidence(value) {
  if (value == null) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format file size in bytes to a human-readable string
 */
export function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

/**
 * Format uptime in seconds to a human-readable string
 */
export function formatUptime(seconds) {
  if (!seconds) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/**
 * Capitalize the first letter of a string
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/**
 * Format current date/time for display
 */
export function formatCurrentTime() {
  return new Intl.DateTimeFormat('en-PK', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date());
}
