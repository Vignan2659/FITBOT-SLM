# Fitness bands and smartwatches

FitBot can use the data from your fitness band or smartwatch: steps, distance, active energy, heart rate, resting heart
rate, HRV, stress, sleep, blood oxygen and recorded workouts. It shows them on the **Bands** page and the dashboard, and
the chat answers questions about your own day with your own numbers ("How did I sleep last night?", "How many steps did
I do today?", "Am I recovered enough to train today?").

Everything stays on your computer. The files are read by the FitBot backend and stored in the same local SQLite
database as your chats; nothing is sent to a cloud service.

## How the data gets in

A band does not talk to a web app on a laptop. It syncs to its phone app (Apple Health, Samsung Health, Huawei Health
and so on), and only some brands offer an online API, which would also mean sending your data through their servers.
Every one of those phone apps can **export** your data as a file, so FitBot imports that file. This works the same for
every brand.

| Band | Export from | File | Brings in |
|---|---|---|---|
| Apple Watch | Health app on the iPhone: your picture, Export All Health Data | `export.zip` | steps, heart rate, resting heart rate, HRV, sleep, blood oxygen, workouts |
| Samsung Galaxy Watch | Samsung Health: Settings, Download personal data | zip of the `Samsung Health` folder, or its CSV files | steps, heart rate, stress, sleep, blood oxygen, workouts |
| Google Pixel Watch, Fitbit | takeout.google.com: Fitbit (and Fit) | `takeout-*.zip` | steps, heart rate, resting heart rate, HRV, stress score, sleep, workouts |
| Huawei Watch, Huawei Band | Huawei Health: Privacy centre, Request your data | the zip Huawei emails you | steps, heart rate, resting heart rate, stress, sleep, workouts |
| OnePlus Watch, OnePlus Band | OHealth shares to Health Connect; phone Settings, Health Connect, Export | Health Connect export zip | steps, heart rate, sleep, blood oxygen, workouts |
| Noise | NoiseFit syncs to Google Fit or Apple Health; export from there, or fill the CSV template | Takeout zip, `export.zip` or CSV | steps, heart rate, sleep, stress |
| WHOOP | WHOOP app: App settings, Data export | `my_whoop_data_*.zip` | resting heart rate, HRV, recovery, sleep, blood oxygen, workouts |
| Garmin, Amazfit, Xiaomi, boAt, others | the app's CSV export, or the FitBot CSV template | CSV | whatever columns the file has |

The Bands page shows these steps for the band you pick. FitBot recognises the format from the file itself, so
picking the wrong brand does not matter. Importing the same file again does not duplicate anything.

You can also type a day in by hand (useful for bands with no export), and download a CSV template with the column
names FitBot understands.

### Reading the files

`backend/app/services/wearables.py` has one reader per format:

* **Apple Health** `export.xml`: read as a stream, so exports of several gigabytes work. Steps and distance are counted
  per source and the largest source wins, because an iPhone and an Apple Watch both count the same steps. Sleep counts
  only the asleep stages, not time in bed, and a night belongs to the day you wake up.
* **Samsung Health** CSVs: the first line of each file is metadata and the column names carry a prefix; times are UTC
  with a separate offset column, which is applied.
* **Google Takeout**: Fitbit's JSON files (steps, heart rate, resting heart rate, sleep, exercises) and CSVs (HRV,
  stress score), and Google Fit's daily activity metrics.
* **Health Connect** (Android, used by OnePlus and many others): a SQLite database; table and column names are looked
  up when the file is read because they differ a little between Android versions.
* **Huawei Health**: JSON files whose layout changes between app versions, so the reader walks the whole document and
  picks up sample points, daily sport totals and workout summaries.
* **WHOOP**: the physiological cycles and workouts CSVs.
* **Any CSV**: common column names ("Steps", "Resting Heart Rate", "Sleep Hours", "HRV", "Stress" ...) are matched.

Values outside a plausible range (a resting heart rate of 300, 999,999 steps) are dropped. Only the last 13 months are
kept.

### Stress

Stress is stored on a 0 to 100 scale where higher means more stress. Samsung and Huawei give a stress score
directly. Fitbit's stress management score and WHOOP's recovery score are the other way round (higher is better), so
they are flipped. For bands without any stress score, FitBot **estimates** one from how today's resting heart rate and
HRV compare with your own last four weeks: a resting heart rate well above your usual or an HRV well below it usually
reflects strain (poor sleep, hard training, illness or mental stress). Estimated values are marked "estimated" in the
app. These are wellness estimates, not medical measurements.

## Live heart rate

Many bands and all chest straps can broadcast heart rate over Bluetooth with the standard Heart Rate service (WHOOP,
most Huawei watches, Garmin, Polar, Coros, Amazfit, Fitbit Charge 6). In Chrome or Edge the Bands page can connect to
them directly with Web Bluetooth and shows your heart rate, the zone (from 220 minus your age), a live graph and the
session average and maximum. The session can be saved as a workout. Apple Watch does not broadcast heart rate, and
Safari and Firefox have no Web Bluetooth.

## In the chat

When a message asks about your own data ("How many steps did I do today?", "What's my resting heart rate?", "How did I
sleep last night?", "Should I work out today or rest?"), the chat loads your band summary and gives the model two
reference lines: the latest day's numbers and the 7 day averages with any notable change. The model writes the answer
around those numbers, and the same numbers are shown in a card under the answer, so they never depend on the model's
wording. General questions ("How much should I sleep?") are answered as before. If you ask about your own numbers before
importing anything, FitBot says how to connect a band instead of guessing.

When a request for a plan mentions your sleep or stress ("Give me a 3 day plan that fits my sleep and stress this
week"), the plan is built as usual and your band numbers are added to the model's references.

## API

| Endpoint | |
|---|---|
| `GET /wearables/brands` | the supported bands with export steps |
| `GET /wearables/template.csv` | the CSV template |
| `POST /wearables/import?brand=&filename=` | body: the export file as raw bytes (up to 3 GB) |
| `GET /wearables/summary?days=14` | latest day, daily series, 7 day averages, insights, workouts, imported files |
| `PUT /wearables/day` | type in one day |
| `POST /wearables/live` | save a live heart rate session |
| `DELETE /wearables/data?source=` | delete one source or all band data |

All of them except the first two need a logged in user, and every row belongs to that user only.

## Database

```
wearable_daily     user_id, day, source, steps, distance_km, active_kcal, resting_hr, avg_hr, max_hr, min_hr,
                   hrv_ms, stress, sleep_minutes, spo2        (one row per user, day and source)
wearable_workouts  user_id, source, start, activity, minutes, kcal, avg_hr, max_hr, distance_km, steps
wearable_imports   user_id, source, format, filename, days, workouts, first_day, last_day, created_at
```

The tables are created automatically on start. Several sources for the same day are merged when read: totals take the
largest source, the other values the first one available.

## Tests

`backend/tests/test_wearables.py` builds small export files in each brand's published format
(`backend/tests/band_samples.py`) and checks every reader, the import API, merging, the stress estimate, privacy
between users and the chat answers. `frontend/src/test/components.test.jsx` checks the band card and the Bluetooth heart
rate parser.

## Limits

* The data is as fresh as the last export. Exporting takes a minute in each phone app; automatic syncing would need
  each brand's cloud API and a developer registration with every brand.
* Huawei and Samsung change their export layouts from time to time. If numbers are missing after an import, the CSV
  template always works.
* Noise and OnePlus have no export of their own; they go through Google Fit, Apple Health or Health Connect.
* Live heart rate needs Chrome or Edge and a band that broadcasts heart rate.
