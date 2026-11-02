#!/usr/bin/env python3
"""Generate a one-item "Today in Harrow" RSS feed (weather + TfL status). Standard library only."""
import json, urllib.request, html, datetime, email.utils, sys
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

TZ = ZoneInfo("Europe/London")
WEATHER_URL = ("https://api.open-meteo.com/v1/forecast?latitude=51.58&longitude=-0.34"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
    "precipitation_sum,wind_speed_10m_max&timezone=Europe%2FLondon&forecast_days=1")
TFL_URL = "https://api.tfl.gov.uk/Line/metropolitan,jubilee,bakerloo,lioness/Status"
LINE_NAMES = {"metropolitan": "Metropolitan", "jubilee": "Jubilee", "bakerloo": "Bakerloo",
              "lioness": "Lioness (Overground, Watford DC line)"}
WMO = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Cloudy",45:"Fog",48:"Freezing fog",
 51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",56:"Light freezing drizzle",57:"Freezing drizzle",
 61:"Light rain",63:"Rain",65:"Heavy rain",66:"Light freezing rain",67:"Freezing rain",
 71:"Light snow",73:"Snow",75:"Heavy snow",77:"Snow grains",80:"Light showers",81:"Showers",
 82:"Heavy showers",85:"Light snow showers",86:"Snow showers",95:"Thunderstorms",
 96:"Thunderstorms with hail",99:"Thunderstorms with heavy hail"}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TodayInHarrowFeed/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def weather():
    try:
        d = get(WEATHER_URL)["daily"]
        words = WMO.get(d["weather_code"][0], "Mixed conditions")
        hi, lo = round(d["temperature_2m_max"][0]), round(d["temperature_2m_min"][0])
        rain, mm = d["precipitation_probability_max"][0], d["precipitation_sum"][0]
        wind = round(d["wind_speed_10m_max"][0] * 0.621371)
        short = f"{words}, {hi}°C"
        body = (f"{words}. High {hi}°C, low {lo}°C. Chance of rain {rain}% "
                f"({mm} mm expected). Wind up to {wind} mph.")
        return short, body
    except Exception as e:
        print("weather failed:", e, file=sys.stderr)
        return None, "Weather data is unavailable this morning."

def tfl():
    try:
        rows = []
        for line in get(TFL_URL):
            sts = line.get("lineStatuses") or []
            name = LINE_NAMES.get(line["id"], line["name"])
            if not sts:
                rows.append(f"<b>{escape(name)}:</b> status unavailable"); continue
            parts = []
            for s in sts:
                if s.get("reason"):
                    parts.append(escape(s["reason"].strip()))
                else:
                    parts.append(escape(s["statusSeverityDescription"].capitalize()))
            rows.append(f"<b>{escape(name)}:</b> " + " ".join(dict.fromkeys(parts)))
        return rows
    except Exception as e:
        print("tfl failed:", e, file=sys.stderr)
        return ["Travel status is unavailable this morning. Check tfl.gov.uk before you travel."]

def main(out="feed.xml"):
    now = datetime.datetime.now(TZ)
    short, wbody = weather()
    lines = tfl()
    title = f"Today in Harrow: {short}" if short else "Today in Harrow"
    desc = (f"<p><b>Weather:</b> {escape(wbody)}</p><p><b>Travel:</b></p><ul>"
            + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"
            "<p>Sources: Open-Meteo and Transport for London.</p>")
    date = now.strftime("%Y-%m-%d")
    pub = email.utils.format_datetime(now)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Today in Harrow</title>
<link>https://harrowonline.org/</link>
<description>Daily Harrow weather and travel status</description>
<language>en-gb</language>
<lastBuildDate>{pub}</lastBuildDate>
<ttl>60</ttl>
<item>
<title>{escape(title)}</title>
<link>https://harrowonline.org/</link>
<guid isPermaLink="false">today-in-harrow-{date}</guid>
<pubDate>{pub}</pubDate>
<description><![CDATA[{desc}]]></description>
</item>
</channel>
</rss>
"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml)

if __name__ == "__main__":
    main(*sys.argv[1:])
