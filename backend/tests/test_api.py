import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app("sqlite+aiosqlite:///:memory:")) as client:
        yield client


def test_catalog_and_persistent_guest_wallet(client):
    catalog = {game['id']:game for game in client.get('/api/games').json()}
    assert catalog['royal']['reels'] == 3
    assert catalog['ocean']['reels'] == 5
    first = client.get('/api/session')
    assert first.status_code == 200
    assert first.json()['balance'] == 10000
    assert 'HttpOnly' in first.headers['set-cookie']
    assert client.get('/api/session').json()['id'] == first.json()['id']


def test_spin_is_persisted_and_replay_is_idempotent(client):
    client.get('/api/session')
    request = {'game': 'moon', 'bet': 20, 'requestId': 'bc022243-f873-48ae-b6d3-a013ff5ea9b3'}
    result = client.post('/api/spin', json=request)
    assert result.status_code == 200
    data = result.json()
    assert len(data['grid']) == 5
    assert data['balance'] == 9980 + data['payout']
    assert client.post('/api/spin', json=request).json() == data
    assert client.get('/api/session').json()['balance'] == data['balance']
    assert len(client.get('/api/history').json()) == 1
    assert client.get('/api/rounds/' + data['id']).json() == data


def test_daily_claim_and_invalid_input(client):
    assert client.post('/api/bonus', json={}).status_code == 401
    client.get('/api/session')
    assert client.post('/api/bonus', json={}).json()['balance'] == 11500
    assert client.post('/api/bonus', json={}).status_code == 409
    for bet in (-10, 20.5, True):
        response = client.post('/api/spin', json={'game':'moon', 'bet':bet, 'requestId':'bc022243-f873-48ae-b6d3-a013ff5ea9b3'})
        assert response.status_code in (400, 422)
        assert 'error' in response.json()
    assert client.get('/api/session').json()['balance'] == 11500


def test_api_accepts_custom_wagers_for_new_games_and_rejects_out_of_range(client):
    from uuid import uuid4
    client.get('/api/session')
    result = client.post('/api/spin', json={'game':'royal','bet':37,'requestId':str(uuid4())})
    assert result.status_code == 200
    assert result.json()['cost'] == 37
    assert len(result.json()['grid']) == 3
    for bet in (0,10001):
        assert client.post('/api/spin', json={'game':'ocean','bet':bet,'requestId':str(uuid4())}).status_code == 400


def test_goldrush_cascades_are_saved_and_replayed_with_the_same_wallet(client):
    from uuid import uuid4
    client.get('/api/session')
    assert any(g['id'] == 'goldrush' for g in client.get('/api/games').json())
    request = {'game':'goldrush', 'bet':37, 'requestId':str(uuid4())}
    response = client.post('/api/spin', json=request)
    assert response.status_code == 200
    data = response.json()
    assert data['cascades'][0]['grid'] == data['grid']
    assert data['payout'] == sum(frame['payout'] for frame in data['cascades'])
    assert data['balance'] == 9963 + data['payout']
    assert client.post('/api/spin', json=request).json() == data
    assert client.get('/api/rounds/' + data['id']).json() == data
    assert client.get('/api/session').json()['balance'] == data['balance']


def test_big_bass_fisherman_progress_survives_refresh_and_replay(client,monkeypatch):
    from uuid import uuid4
    from backend.app.api import routes
    from backend.app.services.slots import play as real_play
    def grid():
        return [[f'blank-{c}-{r}' for r in range(3)] for c in range(5)]
    trigger=grid()
    trigger[0][0]=trigger[2][0]=trigger[4][0]='scatter'
    three=grid(); three[0][0]=three[1][0]=three[2][2]='wild'
    one=grid(); one[4][0]='wild'
    frames=iter([trigger,three,one])
    def controlled(game,bet,balance,free_spins=0,**kwargs):
        return real_play(game,bet,balance,free_spins,grid=next(frames),**kwargs)
    monkeypatch.setattr(routes,'play',controlled)
    client.get('/api/session')
    def spin():
        request={'game':'bigbass','bet':20,'requestId':str(uuid4())}
        response=client.post('/api/spin',json=request)
        assert response.status_code==200
        return request,response.json()
    spin()
    spin()
    active=next(r for r in client.get('/api/session').json()['rounds'] if r['game']=='bigbass')
    assert active['feature']['fishermen']==3
    request,result=spin()
    assert result['feature']['fishermen']==4
    assert result['freeSpins']==18
    assert result['feature']['batches']==[{'spins':8,'multiplier':1},{'spins':10,'multiplier':2}]
    assert client.post('/api/spin',json=request).json()==result
    refreshed=next(r for r in client.get('/api/session').json()['rounds'] if r['game']=='bigbass')
    assert refreshed['feature']==result['feature']


def test_saloon_round_is_saved_and_duplicate_request_cannot_charge_twice(client):
    from uuid import uuid4
    client.get('/api/session')
    catalog = client.get('/api/games').json()
    assert any(game['id'] == 'saloon' for game in catalog)
    request = {'game':'saloon','bet':37,'requestId':str(uuid4())}
    response = client.post('/api/spin', json=request)
    assert response.status_code == 200
    result = response.json()
    assert result['game'] == 'saloon'
    assert result['cost'] == 37
    assert len(result['grid']) == 3
    assert result['balance'] == 9963 + result['payout']
    assert client.post('/api/spin', json=request).json() == result
    assert client.get('/api/rounds/' + result['id']).json() == result
    assert client.get('/api/session').json()['balance'] == result['balance']
