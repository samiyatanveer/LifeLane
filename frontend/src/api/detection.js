import client from './client';

export async function postDetection(file, approach, junctionId) {
  const form = new FormData();
  form.append('file', file);
  form.append('approach', approach);
  form.append('junction_id', junctionId);
  const { data } = await client.post('/detect', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getDetections(limit = 20) {
  const { data } = await client.get('/detections', { params: { limit } });
  return data;
}
