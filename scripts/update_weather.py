#!/usr/bin/env python3
import os
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
OUT=Path('/var/www/mywebsite/start/weather.json')
LAT = float(
    os.environ.get(
        "WEATHER_LAT",
        "51.5074",
    )
)

LON = float(
    os.environ.get(
        "WEATHER_LON",
        "-0.1278",
    )
)

TIMEZONE = os.environ.get(
    "WEATHER_TIMEZONE",
    "Europe/London",
)
CODES={0:('Clear','☀️'),1:('Mainly clear','🌤'),2:('Partly cloudy','⛅'),3:('Overcast','☁️'),45:('Fog','🌫'),48:('Fog','🌫'),51:('Drizzle','🌦'),53:('Drizzle','🌦'),55:('Drizzle','🌧'),61:('Rain','🌧'),63:('Rain','🌧'),65:('Heavy rain','🌧'),71:('Snow','🌨'),73:('Snow','🌨'),75:('Heavy snow','🌨'),80:('Showers','🌦'),81:('Showers','🌧'),82:('Heavy showers','🌧'),95:('Thunderstorm','⛈')}
def main():
 q=urllib.parse.urlencode({'latitude':LAT,'longitude':LON,'current':'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m','daily':'weather_code,temperature_2m_max,temperature_2m_min','timezone':TIMEZONE,'forecast_days':4})
 with urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?'+q,timeout=12) as r:d=json.load(r)
 c=d['current'];cond,icon=CODES.get(c['weather_code'],('Weather','⛅'));daily=[]
 for day,code,hi,lo in zip(d['daily']['time'],d['daily']['weather_code'],d['daily']['temperature_2m_max'],d['daily']['temperature_2m_min']):
  daily.append({'day':datetime.fromisoformat(day).strftime('%a'),'icon':CODES.get(code,('', '·'))[1],'high':round(hi),'low':round(lo)})
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'place':'Your City, UK','temperature':round(c['temperature_2m']),'feels_like':round(c['apparent_temperature']),'humidity':round(c['relative_humidity_2m']),'wind':round(c['wind_speed_10m']),'condition':cond,'icon':icon,'daily':daily}
 OUT.parent.mkdir(parents=True,exist_ok=True);tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2),encoding='utf-8');tmp.replace(OUT);print('Wrote',OUT)
if __name__=='__main__':main()
