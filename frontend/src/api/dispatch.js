import client from './client';

export async function getAmbulances() {
  const { data } = await client.get('/ambulances');
  return data;
}

export async function registerAmbulance(payload) {
  const { data } = await client.post('/ambulances/register', payload);
  return data;
}

export async function getRequests() {
  const { data } = await client.get('/requests');
  return data;
}

export async function createRequest(payload) {
  const { data } = await client.post('/requests', payload);
  return data;
}

export async function updateRequestStatus(id, status) {
  const { data } = await client.patch(`/requests/${id}/status`, { status });
  return data;
}
export async function getRouteOptions(origin_edge, destination_edge) { const { data } = await client.get('/routes/options', { params: { origin_edge, destination_edge } }); return data; }
export async function startTemporaryVerification(payload) { const { data } = await client.post('/temporary-verifications', payload); return data; }
export async function confirmTemporaryVerification(payload) { const { data } = await client.post('/temporary-verifications/confirm', payload); return data; }
export async function authorizePriority(id) { const { data } = await client.post(`/requests/${id}/authorize-priority`); return data; }
