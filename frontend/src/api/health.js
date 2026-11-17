import client from './client';

export async function getHealth() {
  const { data } = await client.get('/health');
  return data;
}

export async function getModelInfo() {
  const { data } = await client.get('/model-info');
  return data;
}

export async function getStats() {
  const { data } = await client.get('/stats');
  return data;
}
