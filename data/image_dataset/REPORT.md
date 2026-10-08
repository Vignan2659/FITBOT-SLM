# Exercise image dataset – cleaning report

Source: [free-exercise-db](https://github.com/yuhonas/free-exercise-db) (Unlicense / public domain), commit cloned to `data/raw/free-exercise-db-repo`. Data collection and cleaning only – **no model was trained**.

## Totals

| | Count |
|---|---:|
| Exercises in source metadata | 876 |
| Exercises with no image in source | 3 (Kettlebell Halo, Kettlebell Halo with Overhead Extension, Kettlebell Overhead Triceps Extension) |
| Images in source | 1746 |
| **Clean images (final dataset)** | **1718** |
| **Unique exercises in final dataset** | **871** |
| Duplicate images moved to `duplicates/` | 25 |
| Rejected images moved to `rejected/` | 3 |

## Duplicates

| Type | Groups | Images kept | Images set aside |
|---|---:|---:|---:|
| Exact | 22 | 22 | 25 |
| Near | 0 | 0 | 0 |
| Similar | 1 | 1 | 0 |

Exact = identical file hash (SHA-256). Near = same photo re-saved / re-used (≤ 1 % of pixels differ after downscaling, CLIP similarity ≥ 0.90), calibrated by viewing the candidate pairs. Perceptual hashes (pHash, dHash) are stored in the manifest; on their own they flagged many *different* photos taken in the same studio, so they were not used as the deciding test. Similar = different exercises whose start photos are almost identical (<= 3 % of pixels differ); both are kept but always placed in the same split. The two frames of one exercise (start / end position) are never treated as duplicates and always share a split.

| Group | Kept image | Duplicates set aside |
|---|---|---|
| dup_001 | 90_90_Hamstring/0.jpg | Leg-Up_Hamstring_Stretch/0.jpg |
| dup_002 | 90_90_Hamstring/1.jpg | Leg-Up_Hamstring_Stretch/1.jpg |
| dup_003 | All_Fours_Quad_Stretch/0.jpg | Cat_Stretch/0.jpg, One_Half_Locust/0.jpg, Rear_Leg_Raises/0.jpg |
| dup_004 | Ankle_On_The_Knee/0.jpg | Hug_Knees_To_Chest/0.jpg |
| dup_005 | Brachialis-SMR/0.jpg | Brachialis-SMR/1.jpg |
| dup_006 | Downward_Facing_Balance/0.jpg | Pyramid/1.jpg |
| dup_007 | Elbows_Back/0.jpg | Standing_Toe_Touches/0.jpg |
| dup_008 | Hamstring_Stretch/0.jpg | Quad_Stretch/0.jpg |
| dup_009 | IT_Band_and_Glute_Stretch/0.jpg | Intermediate_Hip_Flexor_and_Quad_Stretch/0.jpg |
| dup_010 | Latissimus_Dorsi-SMR/0.jpg | Lower_Back-SMR/0.jpg |
| dup_011 | Middle_Back_Stretch/0.jpg | Overhead_Stretch/0.jpg |
| dup_012 | One_Arm_Against_Wall/0.jpg | One_Arm_Against_Wall/1.jpg |
| dup_013 | Reverse_Grip_Bent-Over_Rows/0.jpg | Reverse_Grip_Bent-Over_Rows/1.jpg |
| dup_014 | Seated_Calf_Stretch/0.jpg | Upper_Back-Leg_Grab/0.jpg |
| dup_015 | Seated_Floor_Hamstring_Stretch/0.jpg | Seated_Floor_Hamstring_Stretch/1.jpg |
| dup_016 | Shoulder_Stretch/0.jpg | Tricep_Side_Stretch/0.jpg, Triceps_Stretch/0.jpg |
| dup_017 | Side_Lying_Groin_Stretch/0.jpg | Windmills/0.jpg |
| dup_018 | Standing_Hamstring_and_Calf_Stretch/0.jpg | Standing_Hamstring_and_Calf_Stretch/1.jpg |
| dup_019 | Standing_Hip_Flexors/0.jpg | Standing_Soleus_And_Achilles_Stretch/0.jpg |
| dup_020 | Standing_Hip_Flexors/1.jpg | Worlds_Greatest_Stretch/0.jpg |
| dup_021 | Standing_Pelvic_Tilt/0.jpg | Upper_Back_Stretch/0.jpg |
| dup_022 | The_Straddle/0.jpg | The_Straddle/1.jpg |
| sim_001 (similar, all kept) | Runners_Stretch/0.jpg | - |

## Quality check

| Status | Images |
|---|---:|
| ok | 1741 |
| ok_low_resolution | 2 |
| rejected_irrelevant | 3 |

Every image was decoded fully (no corrupted files) and every image was viewed. Rejected as irrelevant:

* `exercises/Bicycling/0.jpg` – close-up of a helmet buckle
* `exercises/Bicycling/1.jpg` – close-up of a bicycle seat
* `exercises/Skating/0.jpg` – close-up of a helmet

Images that appear under more than one exercise name (start-position photos shared between stretches, etc.) are kept once and noted in the manifest's `notes` column; they are not mislabelled, the source reuses the same photo for related movements.

## Splits (no exercise and no duplicate group appears in more than one split)

| Split | Images | Exercises |
|---|---:|---:|
| train | 1369 (79.7%) | 693 |
| validation | 176 (10.2%) | 90 |
| test | 173 (10.1%) | 88 |

| Category | Train | Validation | Test |
|---|---:|---:|---:|
| cardio | 18 | 4 | 3 |
| olympic weightlifting | 54 | 8 | 8 |
| plyometrics | 98 | 12 | 12 |
| powerlifting | 60 | 8 | 8 |
| strength | 928 | 117 | 116 |
| stretching | 177 | 23 | 22 |
| strongman | 34 | 4 | 4 |

## Images per exercise (clean set)

| Images per exercise | Exercises |
|---:|---:|
| 1 | 24 |
| 2 | 847 |

Full per-exercise list with split and image paths: `exercises.json`; per-image details: `manifest.csv` / `manifest.json` (filename, exercise, resolution, quality status, duplicate status, duplicate group, split).

## Folder layout

```
data/image_dataset/
  clean/{train,validation,test}/<normalized_exercise>/<normalized_exercise>_<frame>.jpg
  duplicates/<duplicate_group>/...        (set aside, not deleted)
  rejected/<reason>/...                    (set aside, not deleted)
  manifest.csv  manifest.json  exercises.json  REPORT.md
```

Rebuild: `.venv/bin/python scripts/image_dataset/extract_features.py && .venv/bin/python scripts/image_dataset/build_dataset.py`
