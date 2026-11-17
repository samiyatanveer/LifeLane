export const JUNCTIONS = [
  { id: 'J1', name: 'Junction 1', label: 'J1' },
  { id: 'J2', name: 'Junction 2', label: 'J2' },
  { id: 'J3', name: 'Junction 3', label: 'J3' },
  { id: 'J4', name: 'Junction 4', label: 'J4' },
];

export const APPROACHES = [
  { value: 'north', label: 'North' },
  { value: 'east', label: 'East' },
  { value: 'south', label: 'South' },
  { value: 'west', label: 'West' },
];

export const SIGNAL_STATES = {
  NORMAL: 'NORMAL',
  SUSPECTED: 'SUSPECTED',
  CONFIRMED: 'CONFIRMED',
  PREPARING: 'PREPARING',
  SERVING: 'SERVING',
  RECOVERING: 'RECOVERING',
};

export const STATE_COLORS = {
  NORMAL: 'green',
  SUSPECTED: 'amber',
  CONFIRMED: 'amber',
  PREPARING: 'orange',
  SERVING: 'red',
  RECOVERING: 'blue',
};

export const API_BASE = '/api';

export const ACCEPTED_AUDIO_TYPES = ['.wav', '.mp3', '.ogg', '.flac'];
export const MAX_FILE_SIZE_MB = 50;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export const SAFETY_RULES = [
  'Audio siren detection must pass confidence threshold',
  'Ambulance identity must be verified in the LifeLane registry',
  'Emergency request must be active and approved',
  'Approach must be clear of conflicting traffic',
  'Signal controller must confirm safe state transition',
  'Passage confirmation must be received within timeout window',
];
