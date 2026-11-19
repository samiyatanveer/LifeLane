import client from './client';
export const login = async (payload) => (await client.post('/auth/login', payload)).data;
export const logout = async () => client.post('/auth/logout');
export const getMe = async () => (await client.get('/auth/me')).data;
export const checkRegistrationAvailability = async (registration_number) => (await client.get('/auth/availability', { params: { registration_number } })).data;
export const forgotPassword = async (payload) => (await client.post('/auth/forgot-password', payload)).data;
export const resetPassword = async (payload) => (await client.post('/auth/reset-password', payload)).data;
