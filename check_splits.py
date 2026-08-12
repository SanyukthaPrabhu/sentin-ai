import pandas as pd, numpy as np

align = pd.read_csv('data/weather_cache/label_alignment.csv', parse_dates=['seq_start', 'horizon_start', 'horizon_end'])

TRAIN_END  = '2023-09-30'
VAL_START  = '2023-11-13'
VAL_END    = '2024-02-29'
TEST_START = '2024-04-14'

masks = {
    'TRAIN': align['seq_start'] <= TRAIN_END,
    'VAL':   (align['seq_start'] >= VAL_START) & (align['seq_start'] <= VAL_END),
    'TEST':  align['seq_start'] >= TEST_START,
}

for name, mask in masks.items():
    sub = align[mask]
    pos = int(sub['label'].sum())
    neg = int((sub['label'] == 0).sum())
    print(f"{name}: {len(sub)} samples  pos={pos}  neg={neg}")
    if len(sub) > 0:
        print(f"  seq_start:     {sub['seq_start'].min().date()} -> {sub['seq_start'].max().date()}")
        print(f"  horizon_start: {sub['horizon_start'].min().date()} -> {sub['horizon_start'].max().date()}")
        print(f"  horizon_end:   {sub['horizon_end'].min().date()} -> {sub['horizon_end'].max().date()}")
    print()
