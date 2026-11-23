import asyncio
import uuid

from tests.test_api import _registration_payload, client


async def test_request_is_processed_without_dashboard(client):
    hospital = await client.post('/api/hospitals', json={
        'name': 'Lifecycle Hospital', 'address': 'Test Road', 'city': 'Lahore',
        'province': 'Punjab', 'latitude': 31.52, 'longitude': 74.35,
        'hospital_type': 'General',
    }, headers=await _management_headers(client))
    assert hospital.status_code == 201
    registered = await client.post('/api/ambulances/register', json=_registration_payload(f'LHR-LIFE-{uuid.uuid4().hex[:5]}'))
    assert registered.status_code == 201
    headers = {'Authorization': f"Bearer {registered.json()['access_token']}"}
    created = await client.post('/api/requests', json={
        'hospital_id': hospital.json()['id'], 'origin_latitude': 31.51,
        'origin_longitude': 74.34, 'location_source': 'GPS', 'junction_id': 'J1',
        'approach': 'N', 'origin_edge': 'A', 'destination_edge': 'B',
    }, headers=headers)
    assert created.status_code == 201
    request_id = created.json()['request_id']
    for _ in range(30):
        current = await client.get(f'/api/requests', headers=headers)
        row = next(item for item in current.json() if item['request_id'] == request_id)
        if row['status'] == 'COMPLETED':
            break
        await asyncio.sleep(0.05)
    assert row['status'] == 'COMPLETED'
    history = await client.get(f'/api/requests/{request_id}/transitions', headers=headers)
    assert [item['to_status'] for item in history.json()] == [
        'VALIDATING', 'AUTHORIZED', 'ROUTE_PREPARATION', 'SIGNAL_COORDINATION',
        'CORRIDOR_READY', 'AMBULANCE_PASSAGE', 'COMPLETED'
    ]
    import backend.database as database
    from backend.services.automated_dispatch import process_request_by_id
    await process_request_by_id(request_id, database.AsyncSessionLocal)
    history_again = await client.get(f'/api/requests/{request_id}/transitions', headers=headers)
    assert history_again.json() == history.json()


async def _management_headers(client):
    response = await client.post('/api/auth/login', json={'username': 'dispatcher', 'password': 'dispatcher-password'})
    return {'Authorization': f"Bearer {response.json()['access_token']}"}
