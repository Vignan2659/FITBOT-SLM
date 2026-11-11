"""Small sample export files in each brand's format, written from the published layout of each export
(Apple Health export.xml, Samsung Health CSVs, Google Takeout Fit + Fitbit, WHOOP CSVs, Health Connect SQLite,
Huawei Health JSON, a plain CSV). Used by test_wearables.py; run directly to write them to a folder:

    python tests/band_samples.py /tmp/band-samples
"""
import json, os, sqlite3, sys, zipfile
from datetime import date, datetime, timedelta

T = date(2026, 11, 10)          # "today" in the samples


def build(out):
    os.makedirs(out, exist_ok=True)
    _build(str(out))
    return out


def _build(out):
    def d(i): return T-timedelta(days=i)
    # Apple
    recs=[]
    for i in range(10):
        day=d(i).isoformat()
        for src,n in (("Vignan's Apple Watch",4000+100*i),("iPhone",1500)):
            recs.append(f'<Record type="HKQuantityTypeIdentifierStepCount" sourceName="{src}" unit="count" startDate="{day} 09:00:00 +0530" endDate="{day} 09:30:00 +0530" value="{n}"/>')
            recs.append(f'<Record type="HKQuantityTypeIdentifierStepCount" sourceName="{src}" unit="count" startDate="{day} 18:00:00 +0530" endDate="{day} 18:30:00 +0530" value="{n}"/>')
        for hr in (58,72,131):
            recs.append(f'<Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min" startDate="{day} 10:00:00 +0530" endDate="{day} 10:00:00 +0530" value="{hr}"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch" unit="count/min" startDate="{day} 00:00:00 +0530" endDate="{day} 23:59:00 +0530" value="{56+ (8 if i==0 else 0)}"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="{day} 03:00:00 +0530" endDate="{day} 03:00:00 +0530" value="{60-i}"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Watch" unit="kcal" startDate="{day} 10:00:00 +0530" endDate="{day} 11:00:00 +0530" value="420"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierDistanceWalkingRunning" sourceName="Watch" unit="km" startDate="{day} 10:00:00 +0530" endDate="{day} 11:00:00 +0530" value="5.2"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierOxygenSaturation" sourceName="Watch" unit="%" startDate="{day} 03:00:00 +0530" endDate="{day} 03:00:00 +0530" value="0.97"/>')
        prev=d(i+1).isoformat()
        recs.append(f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" startDate="{prev} 23:30:00 +0530" endDate="{day} 03:00:00 +0530" value="HKCategoryValueSleepAnalysisAsleepCore"/>')
        recs.append(f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" startDate="{day} 03:00:00 +0530" endDate="{day} 06:30:00 +0530" value="HKCategoryValueSleepAnalysisAsleepDeep"/>')
        recs.append(f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" startDate="{prev} 23:00:00 +0530" endDate="{day} 06:45:00 +0530" value="HKCategoryValueSleepAnalysisInBed"/>')
    wk=f'<Workout workoutActivityType="HKWorkoutActivityTypeTraditionalStrengthTraining" duration="42.5" durationUnit="min" sourceName="Watch" startDate="{d(1)} 18:00:00 +0530" endDate="{d(1)} 18:42:30 +0530"><WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="310" unit="kcal"/><WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="128" minimum="90" maximum="161" unit="count/min"/></Workout>'
    xml='<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_IN"><ExportDate value="2026-11-10 20:00:00 +0530"/><Me/>'+"".join(recs)+wk+'</HealthData>'
    with zipfile.ZipFile(f"{out}/apple_export.zip","w") as z: z.writestr("apple_health_export/export.xml",xml); z.writestr("apple_health_export/export_cda.xml","<x/>")
    # Samsung
    with zipfile.ZipFile(f"{out}/samsung.zip","w") as z:
        rows="com.samsung.shealth.tracker.pedometer_day_summary,6312001,3\n"+"step_count,distance,calorie,day_time,deviceuuid\n"
        for i in range(5):
            ms=int(datetime(d(i).year,d(i).month,d(i).day).timestamp()*1000) + 19800*1000
            rows+=f"{7000+i},5100.5,301.2,{ms},watch\n{2000},1400,90,{ms},phone\n"
        z.writestr("samsunghealth_x/com.samsung.shealth.tracker.pedometer_day_summary.20261110.csv",rows)
        hr="com.samsung.shealth.tracker.heart_rate,6312001,2\ncom.samsung.health.heart_rate.start_time,com.samsung.health.heart_rate.heart_rate,com.samsung.health.heart_rate.time_offset\n"
        hr+=f"{d(0)} 04:10:00.000,64,UTC+0530\n{d(0)} 12:10:00.000,98,UTC+0530\n"
        z.writestr("samsunghealth_x/com.samsung.shealth.tracker.heart_rate.20261110.csv",hr)
        st="com.samsung.shealth.stress,6312001,2\nstart_time,score,time_offset\n"+f"{d(0)} 05:00:00.000,40,UTC+0530\n{d(0)} 09:00:00.000,60,UTC+0530\n"
        z.writestr("samsunghealth_x/com.samsung.shealth.stress.20261110.csv",st)
        sl="com.samsung.shealth.sleep,6312001,1\ncom.samsung.health.sleep.start_time,com.samsung.health.sleep.end_time,com.samsung.health.sleep.time_offset\n"+f"{d(1)} 18:00:00.000,{d(0)} 01:00:00.000,UTC+0530\n"
        z.writestr("samsunghealth_x/com.samsung.shealth.sleep.20261110.csv",sl)
        ex="com.samsung.shealth.exercise,6312001,1\ncom.samsung.health.exercise.start_time,com.samsung.health.exercise.exercise_type,com.samsung.health.exercise.duration,com.samsung.health.exercise.calorie,com.samsung.health.exercise.mean_heart_rate,com.samsung.health.exercise.max_heart_rate,com.samsung.health.exercise.distance,com.samsung.health.exercise.time_offset\n"+f"{d(0)} 01:00:00.000,1002,1800000,250,140,165,5000,UTC+0530\n"
        z.writestr("samsunghealth_x/com.samsung.shealth.exercise.20261110.csv",ex)
    # Google Takeout: Fit + Fitbit
    with zipfile.ZipFile(f"{out}/takeout.zip","w") as z:
        fit="Date,Move Minutes count,Calories (kcal),Distance (m),Heart Points,Heart Minutes,Average heart rate (bpm),Max heart rate (bpm),Min heart rate (bpm),Step count,Walking duration (ms),Sleep duration (ms)\n"
        for i in range(4): fit+=f"{d(i)},60,2100,4300,20,20,74,140,52,{6000+i},1800000,25200000\n"
        z.writestr("Takeout/Fit/Daily activity metrics/Daily activity metrics.csv",fit)
        z.writestr("Takeout/Fitbit/Global Export Data/steps-2026-11-01.json",json.dumps([{"dateTime":d(0).strftime("%m/%d/%y")+" 08:00:00","value":"3000"},{"dateTime":d(0).strftime("%m/%d/%y")+" 18:00:00","value":"5200"}]))
        z.writestr("Takeout/Fitbit/Global Export Data/heart_rate-2026-11-10.json",json.dumps([{"dateTime":d(0).strftime("%m/%d/%y")+" 08:00:00","value":{"bpm":61,"confidence":3}},{"dateTime":d(0).strftime("%m/%d/%y")+" 18:00:00","value":{"bpm":119,"confidence":3}}]))
        z.writestr("Takeout/Fitbit/Global Export Data/resting_heart_rate-2026-01-01.json",json.dumps([{"dateTime":d(0).strftime("%m/%d/%y")+" 00:00:00","value":{"date":d(0).strftime("%m/%d/%y"),"value":57.4,"error":6}}]))
        z.writestr("Takeout/Fitbit/Global Export Data/sleep-2026-11-01.json",json.dumps([{"logId":1,"dateOfSleep":str(d(0)),"minutesAsleep":431}]))
        z.writestr("Takeout/Fitbit/Global Export Data/exercise-0.json",json.dumps([{"activityName":"Run","startTime":d(1).strftime("%m/%d/%y")+" 07:00:00","activeDuration":1500000,"calories":260,"averageHeartRate":150,"distance":2.5,"distanceUnit":"Mile","steps":4100}]))
        z.writestr("Takeout/Fitbit/Stress Score/Stress Score.csv",f"DATE,UPDATED_AT,STRESS_SCORE\n{d(0)}T00:00:00,x,78\n")
        z.writestr("Takeout/Fitbit/Heart Rate Variability/Daily Heart Rate Variability Summary - 2026-11-(10).csv",f"timestamp,rmssd,nremhr,entropy\n{d(0)}T00:00:00,41.5,55,2\n")
    # WHOOP
    with zipfile.ZipFile(f"{out}/whoop.zip","w") as z:
        c="Cycle start time,Cycle end time,Cycle timezone,Recovery score %,Resting heart rate (bpm),Heart rate variability (ms),Skin temp (celsius),Blood oxygen %,Day Strain,Energy burned (cal),Max HR (bpm),Average HR (bpm),Sleep onset,Wake onset,Sleep performance %,Respiratory rate (rpm),Asleep duration (min),In bed duration (min)\n"
        for i in range(3): c+=f"{d(i+1)} 23:10:00,{d(i)} 23:00:00,UTC+05:30,{66-i},54,71,33.1,96.5,11.2,2350,171,69,{d(i+1)} 23:20:00,{d(i)} 06:50:00,88,15.1,412,450\n"
        z.writestr("physiological_cycles.csv",c)
        z.writestr("workouts.csv",f"Cycle start time,Cycle end time,Cycle timezone,Workout start time,Workout end time,Duration (min),Activity name,Activity Strain,Energy burned (cal),Max HR (bpm),Average HR (bpm),Distance (meters)\n{d(1)} 23:10:00,{d(0)} 23:00:00,UTC+05:30,{d(0)} 07:00:00,{d(0)} 07:48:00,48,Weightlifting,9.8,402,158,121,\n")
        z.writestr("sleeps.csv","Cycle start time\n")
    # Health Connect
    db=f"{out}/hc.db"
    if os.path.exists(db): os.remove(db)
    con=sqlite3.connect(db)
    con.execute("create table steps_record_table(row_id integer primary key, start_time integer, end_time integer, start_zone_offset integer, count integer, app_info_id integer)")
    con.execute("create table heart_rate_record_series_table(parent_key integer, beats_per_minute integer, epoch_millis integer)")
    con.execute("create table sleep_session_record_table(row_id integer primary key, start_time integer, end_time integer, start_zone_offset integer, end_zone_offset integer, app_info_id integer)")
    con.execute("create table exercise_session_record_table(row_id integer primary key, start_time integer, end_time integer, start_zone_offset integer, exercise_type integer, title text)")
    con.execute("create table resting_heart_rate_record_table(row_id integer primary key, time integer, zone_offset integer, beats_per_minute integer)")
    ms=lambda dt:int((dt-datetime(1970,1,1)).total_seconds()*1000)-19800*1000
    for i in range(3):
        dd=datetime(d(i).year,d(i).month,d(i).day)
        con.execute("insert into steps_record_table(start_time,end_time,start_zone_offset,count,app_info_id) values(?,?,?,?,1)",(ms(dd+timedelta(hours=9)),ms(dd+timedelta(hours=10)),19800,5000+i))
        con.execute("insert into steps_record_table(start_time,end_time,start_zone_offset,count,app_info_id) values(?,?,?,?,1)",(ms(dd+timedelta(hours=1)),ms(dd+timedelta(hours=2)),19800,900))
        con.execute("insert into heart_rate_record_series_table values(1,66,?)",(ms(dd+timedelta(hours=9)),))
        con.execute("insert into heart_rate_record_series_table values(1,142,?)",(ms(dd+timedelta(hours=19)),))
        con.execute("insert into sleep_session_record_table(start_time,end_time,start_zone_offset,end_zone_offset,app_info_id) values(?,?,?,?,1)",(ms(dd-timedelta(hours=1)),ms(dd+timedelta(hours=6)),19800,19800))
        con.execute("insert into resting_heart_rate_record_table(time,zone_offset,beats_per_minute) values(?,?,?)",(ms(dd+timedelta(hours=7)),19800,59))
    con.execute("insert into exercise_session_record_table(start_time,end_time,start_zone_offset,exercise_type,title) values(?,?,?,?,?)",(ms(datetime(T.year,T.month,T.day,18)),ms(datetime(T.year,T.month,T.day,18,35)),19800,83,None))
    con.commit(); con.close()
    with zipfile.ZipFile(f"{out}/health_connect.zip","w") as z: z.write(db,"health_connect_export.db")
    # Huawei
    hw=[{"recordDay":int(d(i).strftime("%Y%m%d")),"sportType":t,"sportBasicInfos":[{"steps":s,"distance":dist,"calorie":cal}]} for i in range(3) for t,s,dist,cal in ((0,8100+i,6000,350000),(5,3000,2100,120000))]
    z=zipfile.ZipFile(f"{out}/huawei.zip","w")
    z.writestr("Health detail data & description/health detail data.json",json.dumps([{"type":7,"samplePoints":[{"key":"DATA_POINT_DYNAMIC_HEARTRATE","startTime":ms(datetime(T.year,T.month,T.day,10))+19800000,"endTime":0,"value":"77"},{"key":"DATA_POINT_REST_HEARTRATE","startTime":ms(datetime(T.year,T.month,T.day,8))+19800000,"value":"60"},{"key":"DATA_POINT_NEW_STRESS","startTime":ms(datetime(T.year,T.month,T.day,11))+19800000,"value":"44"}]}]))
    z.writestr("Sport per minute merged data & description/sport per minute merged data.json",json.dumps(hw))
    z.close()
    open(f"{out}/generic.csv","w").write("Date,Steps,Sleep Hours,Resting Heart Rate,Stress,HRV\n2026-11-09,9100,7.5,57,33,64\n2026-11-10,10250,6.2,61,58,51\n")


if __name__ == "__main__":
    print(sorted(os.listdir(build(sys.argv[1]))))
