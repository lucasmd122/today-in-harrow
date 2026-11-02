# Today in Harrow + Harrow Online Daily automatic send

Two jobs run here on GitHub:

1. **Today in Harrow feed** (`generate_feed.py`): each weekday morning it builds a small feed with Harrow's weather and train status. Live at https://lucasmd122.github.io/today-in-harrow/feed.xml
2. **Daily newsletter** (`send_daily.py`): every Sunday to Thursday at 6pm UK winter time (7pm summer time) it creates the next weekday's newsletter in beehiiv and schedules it for **9:00am London time**. News, What's On and the weather pull fresh at send time.

A monthly "keep alive" job stops GitHub pausing the schedules.

## It is OFF until you turn it on
While it's off, it only does a safe practice run that changes nothing in beehiiv.

## Turn it on
In this repo go to **Settings > Secrets and variables > Actions**:
- **Secrets** tab: add `BEEHIIV_API_KEY` (from beehiiv Settings > API). Never paste it anywhere else.
- **Variables** tab: add `DAILY_SEND_ENABLED` = `true`.
- To test with only your own address first, add `BEEHIIV_TEST_SEGMENT_ID` = the ID of a beehiiv segment that contains only you.
- To send to the real list, delete `BEEHIIV_TEST_SEGMENT_ID` and add `DAILY_SEND_FULL_LIST` = `true`. Without one of these two, it will refuse to schedule.

## Turn it off
Change `DAILY_SEND_ENABLED` to `false` (or delete it). Any issue already scheduled in beehiiv must be unscheduled in beehiiv itself.

## Test it
**Actions** tab > **Send Harrow Online Daily** > **Run workflow**, pick:
- `dry-run`: shows what it would create. Changes nothing.
- `draft`: makes a draft in beehiiv to look at. Sends nothing.
- `schedule`: schedules the next weekday's 9am issue.

It never creates the same day twice, skips weekends, and stops with an error if the news or events feeds are empty or out of date. If a run fails, GitHub emails the account owner.
