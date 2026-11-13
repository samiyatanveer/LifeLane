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
