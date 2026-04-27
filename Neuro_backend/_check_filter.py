import json

with open('video_analysis/analysis_data_filtered.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Frame 6
fr = data['frames'][5]
print(f"Frame {fr['frame_number']} at {fr['timestamp_seconds']}s")
print(f"Relevant texts: {len(fr['relevant_texts'])}")
print()
print("=== DETECTED FIELDS ===")
for k, v in fr['detected_fields'].items():
    if v and v != []:
        print(f"  {k}: {v}")
print()

# Spot-check frames 20, 40, 60
for idx in [19, 39, 59]:
    if idx < len(data['frames']):
        fr2 = data['frames'][idx]
        flds = fr2['detected_fields']
        n = len(fr2['relevant_texts'])
        print(f"--- Frame {fr2['frame_number']} at {fr2['timestamp_seconds']}s (kept: {n}) ---")
        for k, v in flds.items():
            if v and v != []:
                print(f"  {k}: {v}")
        print()
