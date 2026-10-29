from uuid import uuid4
import pytest
from backend.app.services.slots import play


def empty_grid():
    return [[f'blank-{c}-{r}' for r in range(3)] for c in range(5)]


@pytest.mark.parametrize('scatters,spins', [(3,10),(4,15),(5,20)])
def test_big_bass_scatters_award_the_published_free_spins(scatters,spins):
    grid=empty_grid()
    for c in range(scatters):
        grid[c][0]='scatter'
    result=play('bigbass',20,100,grid=grid)
    assert result['bonusAwarded']==spins
    assert result['freeSpins']==spins
    assert result['feature']['batches']==[{'spins':spins,'multiplier':1}]
    assert result['balance']==80


def test_money_fish_are_only_collected_during_free_spins(monkeypatch):
    from backend.app.services import big_bass
    monkeypatch.setattr(big_bass,'choice',lambda values:values[0])
    grid=empty_grid()
    grid[0][0]=grid[1][2]='wild'
    grid[2][1]=grid[4][0]='fish'
    base=play('bigbass',20,100,grid=grid)
    assert base['collectionPayout']==0
    free=play('bigbass',20,5,free_spins=3,grid=grid)
    assert free['collectionPayout']==160 # 2 fish x 2x bet x 2 fishermen.
    assert free['payout']==160
    assert free['balance']==165
    assert free['feature']['fishermen']==2


def test_fourth_fisherman_queues_multiplier_for_the_next_batch(monkeypatch):
    from backend.app.services import big_bass
    monkeypatch.setattr(big_bass,'choice',lambda values:values[0])
    grid=empty_grid(); grid[0][0]='wild'; grid[4][2]='fish'
    feature={'fishermen':3,'batches':[{'spins':2,'multiplier':1}],'awarded':0}
    first=play('bigbass',20,5,free_spins=2,grid=grid,feature=feature)
    assert first['collectionPayout']==40
    assert first['bonusAwarded']==10
    assert first['feature']['batches']==[{'spins':1,'multiplier':1},{'spins':10,'multiplier':2}]
    second=play('bigbass',20,45,free_spins=11,grid=grid,feature=first['feature'])
    assert second['collectionPayout']==40 # The original batch has not ended yet.
    assert second['feature']['batches']==[{'spins':10,'multiplier':2}]
    third=play('bigbass',20,85,free_spins=10,grid=grid,feature=second['feature'])
    assert third['collectionPayout']==80
    assert feature['fishermen']==3 # Input state is immutable.


def test_maximum_fisherman_tier_does_not_retrigger_again(monkeypatch):
    from backend.app.services import big_bass
    monkeypatch.setattr(big_bass,'choice',lambda values:values[0])
    grid=empty_grid(); grid[0][0]='wild'; grid[4][2]='fish'
    feature={'fishermen':12,'batches':[{'spins':1,'multiplier':10}],'awarded':0}
    result=play('bigbass',20,0,free_spins=1,grid=grid,feature=feature)
    assert result['collectionPayout']==400
    assert result['bonusAwarded']==0
    assert result['freeSpins']==0


def test_ten_paylines_and_fractional_virtual_payouts_are_settled_once():
    grid=empty_grid()
    grid[0][1]=grid[1][1]=grid[2][1]='A'
    result=play('bigbass',37,100,grid=grid)
    assert result['lines'][0]['payout']==18.5
    assert result['payout']==18
    assert result['balance']==81
    assert result['paylineCount']==10


def test_base_game_never_generates_fisherman_wilds():
    for _ in range(50):
        result=play('bigbass',20,100)
        assert all('wild' not in reel for reel in result['grid'])
        assert all(reel.count('scatter')<=1 for reel in result['grid'])


def test_feature_limit_credits_only_the_remaining_coins_and_cancels_queued_spins(monkeypatch):
    from backend.app.services import big_bass
    monkeypatch.setattr(big_bass,'choice',lambda values:values[-1])
    grid=empty_grid(); grid[0][0]='wild'; grid[4][2]='fish'
    feature={'fishermen':11,'batches':[{'spins':2,'multiplier':3}],'awarded':100}
    result=play('bigbass',20,5,free_spins=2,grid=grid,feature=feature)
    assert result['payout']==41900
    assert result['balance']==41905
    assert result['freeSpins']==0
    assert result['bonusAwarded']==0
    assert result['bonusTriggered'] is False
    assert result['collectionPayout']==41900
    assert result['winCapped'] is True
