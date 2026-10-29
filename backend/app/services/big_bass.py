"""Virtual-coin recreation of the published fishing feature; original RNG weights.

Sources and deliberate differences: docs/big-bass-sources.md.
"""
from copy import deepcopy
from fractions import Fraction
from secrets import choice

PAYLINES = ((1,1,1,1,1),(0,0,0,0,0),(2,2,2,2,2),(0,1,2,1,0),(2,1,0,1,2),
            (0,0,1,2,2),(2,2,1,0,0),(1,0,0,0,1),(1,2,2,2,1),(0,1,1,1,0))
# Multiples of the total wager. Fractions settle once into whole virtual coins.
PAYS = {
    'float':{2:Fraction(1,2),3:5,4:20,5:200},
    'rod':{3:3,4:15,5:100}, 'dragonfly':{3:2,4:10,5:50},
    'tackle':{3:2,4:10,5:50}, 'fish':{3:1,4:5,5:20},
    **{s:{3:Fraction(1,2),4:Fraction(5,2),5:10} for s in ('A','K','Q','J','10')},
}
REGULAR = ('fish','fish','float','rod','dragonfly','tackle',
           'A','A','A','K','K','K','Q','Q','Q','J','J','J','10','10','10')
FISH_VALUES = (2,)*24+(5,)*14+(10,)*7+(15,)*4+(20,)*3+(25,)*2+(50,2000)
MULTIPLIERS = (1,2,3,10)


def evaluate(grid: list[list[str]], bet: int) -> dict:
    lines=[]
    for index,rows in enumerate(PAYLINES):
        symbols=[grid[c][r] for c,r in enumerate(rows)]
        best=None
        for symbol,table in PAYS.items():
            count=0
            for current in symbols:
                if current not in (symbol,'wild'):
                    break
                count+=1
            if count in table:
                value=Fraction(bet)*table[count]
                if best is None or value>best['exact']:
                    best={'index':index,'symbol':symbol,'count':count,'payout':float(value),
                          'cells':[[c,rows[c]] for c in range(count)],'exact':value}
        if best:
            lines.append(best)
    total=sum((line.pop('exact') for line in lines),Fraction(0))
    return {'lines':lines,'linePayout':float(total)}


def play(bet: int, balance: int, free_spins: int=0, grid: list[list[str]] | None=None,
         feature: dict | None=None) -> dict:
    in_bonus=free_spins>0
    if grid is None:
        grid=[]
        for _ in range(5):
            reel=[]
            for _ in range(3):
                bag=REGULAR+('wild','wild') if in_bonus else REGULAR+('scatter',)
                symbol=choice(bag)
                if symbol=='scatter' and 'scatter' in reel:
                    symbol=choice(REGULAR)
                reel.append(symbol)
            grid.append(reel)
    result=evaluate(grid,bet)
    money=[{'cell':[c,r],'value':choice(FISH_VALUES)*bet}
           for c,reel in enumerate(grid) for r,symbol in enumerate(reel) if symbol=='fish']
    fishermen=sum(symbol=='wild' for reel in grid for symbol in reel) if in_bonus else 0
    scatters=sum(symbol=='scatter' for reel in grid for symbol in reel)
    state=deepcopy(feature) if in_bonus and feature else {
        'fishermen':0,'batches':[{'spins':free_spins,'multiplier':1}] if in_bonus else [],'awarded':0}
    multiplier=state['batches'][0]['multiplier'] if in_bonus else 1
    collection=sum(fish['value'] for fish in money)*fishermen*multiplier
    awarded=0
    if in_bonus:
        previous=min(12,state['fishermen'])
        state['fishermen']=min(12,previous+fishermen)
        for threshold in (4,8,12):
            if previous<threshold<=state['fishermen']:
                state['batches'].append({'spins':10,'multiplier':MULTIPLIERS[threshold//4]})
                awarded+=10
        state['batches'][0]['spins']-=1
        state['batches']=[batch for batch in state['batches'] if batch['spins']>0]
    elif scatters>=3:
        awarded=10+(min(5,scatters)-3)*5
        state['batches']=[{'spins':awarded,'multiplier':1}]
    # A bounded virtual feature; no claim is made about the licensed game's RTP.
    raw=int(Fraction(str(result['linePayout']))+collection)
    payout=min(raw,max(0,2100*bet-state['awarded']))
    state['awarded']+=payout
    capped=state['awarded']>=2100*bet
    if capped:
        state['batches']=[]
        awarded=0
    cost=0 if in_bonus else bet
    return {**result,'game':'bigbass','grid':grid,'bet':bet,'cost':cost,'payout':payout,
            'balance':balance-cost+payout,'lines':result['lines'],'scatters':scatters,
            'freeSpins':sum(batch['spins'] for batch in state['batches']),
            'bonusTriggered':awarded>0,'bonusAwarded':awarded,'multiplier':multiplier,
            'moneyFish':money,'fishermenLanded':fishermen,'collectionPayout':min(collection,payout),
            'feature':state,'paylineCount':10,'winCapped':capped}
