import csv
import json
from argparse import ArgumentParser
from typing import TypedDict
from datetime import date, time, datetime


class EventBase(TypedDict):
    name: str
    date: date
    start_time: time
    end_time: time
    place: str


class Event(EventBase):
    groups: list[str]
    people: list[str]


class EventPersonal(EventBase):
    group: str


class PersonalSchedule(TypedDict):
    person: str
    events: list[EventPersonal]


type EventsByName = dict[str, Event]

type SchedulesByPerson = dict[str, list[EventPersonal]]


def get_datetime(date: str) -> datetime:
    return datetime.strptime(date, "%d/%m/%Y %H:%M")


def add_event(
    event_name: str,
    events_by_name: EventsByName,
    person: str,
    group: str,
    event_date: date,
    start_time: time,
    end_time: time,
    place: str,
):
    if event_name not in events_by_name:
        events_by_name[event_name] = {
            "name": event_name,
            "date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "place": place,
            "groups": [group],
            "people": [person],
        }
        return

    existing_event = events_by_name[event_name]

    for key, new_value in (("people", person), ("groups", group)):
        if person not in existing_event[key]:
            existing_event[key].append(new_value)  # type: ignore

    existing_event["date"] = event_date

    if start_time < existing_event["start_time"]:
        existing_event["start_time"] = start_time

    if end_time > existing_event["end_time"]:
        existing_event["end_time"] = end_time


def add_personal_event(
    event_name: str,
    schedules_by_person: SchedulesByPerson,
    person: str,
    group: str,
    event_date: date,
    start_time: time,
    end_time: time,
    place: str,
):
    personal_event: EventPersonal = {
        "name": event_name,
        "date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "place": place,
        "group": group,
    }

    if person in schedules_by_person:
        schedules_by_person[person].append(personal_event)
    else:
        schedules_by_person[person] = [personal_event]


def get_schedules(
    input_file: str,
) -> tuple[tuple[Event, ...], tuple[PersonalSchedule, ...]]:
    events_by_name: EventsByName = {}
    schedules_by_person: SchedulesByPerson = {}

    with open(input_file, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            event_datetime = get_datetime(row["Start time"])
            event_date = event_datetime.date()
            start_time = event_datetime.time()
            end_time = get_datetime(row["End time"]).time()
            place = row["Place"]
            person = row["Person"]
            group = row["Group"]
            event_name = row["Event"]

            add_event(
                event_name,
                events_by_name,
                person,
                group,
                event_date,
                start_time,
                end_time,
                place,
            )
            add_personal_event(
                event_name,
                schedules_by_person,
                person,
                group,
                event_date,
                start_time,
                end_time,
                place,
            )

    return (
        tuple(events_by_name.values()),
        tuple(
            {
                "person": person,
                "events": sorted(
                    events, key=lambda event: (event["date"], event["start_time"])
                ),
            }
            for person, events in schedules_by_person.items()
        ),
    )


def get_pretty_printed_list(list: list[Event | PersonalSchedule]) -> str:
    return json.dumps(list, default=str, indent=4)


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("input_filepath", type=str)

    all_events, personal_schedule = get_schedules(parser.parse_args().input_filepath)

    print(get_pretty_printed_list(list(all_events)))
    print(get_pretty_printed_list(list(personal_schedule)))
