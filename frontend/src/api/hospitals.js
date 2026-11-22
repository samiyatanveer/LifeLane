import client from './client';

export const listHospitals = async (params = {}) => (await client.get('/hospitals', { params })).data;
export const createHospital = async (payload) => (await client.post('/hospitals', payload)).data;
export const updateHospital = async (id, payload) => (await client.patch(`/hospitals/${id}`, payload)).data;
