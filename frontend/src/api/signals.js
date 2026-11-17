import client from './client';

export async function getSignals() {
  const { data } = await client.get('/signals');
  return data;
}

export async function simulateSignal(junctionId, action, extra = {}) {
  const { data } = await client.post(`/signals/${junctionId}/simulate`, {
    action,
    ...extra,
  });
  return data;
}

export async function getEvents(limit = 20) {
  const { data } = await client.get('/events', { params: { limit } });
  return data;
}
