import client from './client';
export const getManagementOverview = async () => (await client.get('/management/overview')).data;
export const getManagementAmbulances = async (params) => (await client.get('/management/ambulances', { params })).data;
export const getManagementRequests = async (params) => (await client.get('/management/requests', { params })).data;
export const getTemporaryVerifications = async (params) => (await client.get('/management/temporary-verifications', { params })).data;
export const decideTemporaryVerification = async (id, approved) => (await client.post(`/management/temporary-verifications/${id}/decision`, null, { params: { approved } })).data;
export const getStaff = async () => (await client.get('/management/staff')).data;
export const createStaff = async (payload) => (await client.post('/management/staff', payload)).data;
export const getAuditLogs = async () => (await client.get('/management/audit-logs')).data;
