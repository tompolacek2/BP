import requests
import json
import csv
from datetime import datetime, timedelta
import re  # Import regex module
import os  # Import os module for environment variables
from scripts.langfuse import LangfuseConnector
class HealthReact():
    """
    Class to handle fetching and processing health data from the HealthReact API.
    """

    # Define available data types
    DATA_TYPES = [
        "STEPS", "CALORIES", "DISTANCE", "ELEVATION",
        "MINUTES_FAIRLY_ACTIVE", "MINUTES_LIGHTLY_ACTIVE",
        "MINUTES_SEDENTARY", "MINUTES_VERY_ACTIVE", "FLOORS",
        "HR", "RESTING"
    ]

    # Define available aggregation methods
    AGGREGATIONS = ["RAW", "AVARAGE", "MAX", "MIN"]

    # Regex to parse the dynamic option format TYPE_AGGREGATION_DAILY_XX
    OPTION_REGEX = re.compile(r"(\w+)_(" + "|".join(AGGREGATIONS) + r")_DAILY_(\d{2})$")
    TODAY_REGEX = re.compile(r"(\w+)_DAILY_TODAY$")

    def __init__(self, api_key: str, health_check_url: str = 'https://osu.hrc1.cat4.uhk.cz/researcher-api/rest/'):
        """
        Initialize the HealthReact class.

        Args:
            api_key (str): The API key for authentication.
            health_check_url (str): The base URL for the HealthReact API.
        """
        self.health_check_url = health_check_url
        self.headers = {
            'accept': "application/json",
            'Authorization': f'Bearer {api_key}'
        }
        self.headers_csv = {
            'accept': "text/csv",
            'Authorization': f'Bearer {api_key}'
        }

    def get_user_available_data_names(self, user_id: str = None):
        """
        Vrací seznam uživatelů s jejich id, jménem a seznamem recordType.
        Pokud je zadáno user_id, vrací pouze pro daného uživatele, jinak pro všechny.
        """
        url = f'{self.health_check_url}export/data/last/all'
        response = requests.get(url, headers=self.headers)
        data = json.loads(response.text)

        users = []
        for user_data in data:
            uid = str(user_data.get("userMapper", {}).get("id"))
            name = user_data.get("userMapper", {}).get("fullName", "")
            record_types = [record.get("recordType") for record in user_data.get("records", [])]
            if user_id is None or uid == str(user_id):
                users.append({
                    "id": uid,
                    "name": name,
                    "recordTypes": record_types
                })
        return users if users else None

    def get_basic_data(self, type: str, from_date: str, to_date: str, user_id: str) -> str:
        """
        Retrieve basic data for the user.

        Returns:
            str: CSV data as a string.
        """
        url = f'{self.health_check_url}export/data/{type}/{user_id}/date/{from_date}/{to_date}'
        response = requests.get(url, headers=self.headers_csv)
        return response.text

    def get_available_data(self, user_record_types, applicant: str = "user"):
        """
        Generates a list of available data options based on user's record types
        and defined aggregations. Includes dynamic XX day options.
        """
        available_options = []
        relevant_types = self.DATA_TYPES
        if applicant == "user":
            # Filter DATA_TYPES based on what the user actually has, if provided
            if user_record_types:
                relevant_types = [rt for rt in user_record_types if rt in self.DATA_TYPES]
            else:
                # If user types are unknown, cautiously offer nothing specific for user?
                # Or offer all possible? Let's offer all for now, validation happens later.
                pass  # Keep relevant_types as all DATA_TYPES

        for data_type in relevant_types:
            # Add dynamic XX options
            for agg in self.AGGREGATIONS:
                available_options.append(f"{data_type}_{agg}_DAILY_XX")
            # Add specific TODAY option
            available_options.append(f"{data_type}_DAILY_TODAY")

        # If applicant is not user (e.g., default), provide all possible combinations
        if applicant != "user":
            all_options = []
            for data_type in self.DATA_TYPES:
                for agg in self.AGGREGATIONS:
                    all_options.append(f"{data_type}_{agg}_DAILY_XX")
                all_options.append(f"{data_type}_DAILY_TODAY")
            return all_options

        return available_options

    def get_data_for_option(self, option: str, user_id: str):
        """
        Fetches and processes data based on the specified option string.
        Handles TYPE_AGGREGATION_DAILY_XX and TYPE_DAILY_TODAY formats.
        """
        print(f"Getting data for option: {option}, User ID: {user_id}")
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # Try matching TYPE_AGGREGATION_DAILY_XX format
        match_xx = self.OPTION_REGEX.match(option)
        # Try matching TYPE_DAILY_TODAY format
        match_today = self.TODAY_REGEX.match(option)

        if match_xx:
            data_type, aggregation, days_str = match_xx.groups()
            days = int(days_str)
            if days <= 0:
                raise ValueError("Number of days (XX) must be positive.")

            from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            to_date = today_str  # Fetch up to today

            print(f"Fetching {data_type} data for {days} days ({from_date} to {to_date})")
            raw_data_csv = self.get_basic_data(data_type, from_date, to_date, user_id)
            data_list = self._parse_csv_data(raw_data_csv)

            if not data_list:
                print("No data found for the period.")
                # Return appropriate zero/empty value based on aggregation
                if aggregation == "RAW":
                    return "[]"
                else:
                    return 0

            print(f"Processing aggregation: {aggregation}")
            if aggregation == "RAW":
                return self.dense_basic_data_to_days(data_list)
            elif aggregation == "AVARAGE":
                days_dict = self._group_data_by_day(data_list)
                return sum(days_dict.values()) / len(days_dict) if days_dict else 0
            elif aggregation == "MAX":
                days_dict = self._group_data_by_day(data_list)
                return max(days_dict.values()) if days_dict else 0
            elif aggregation == "MIN":
                days_dict = self._group_data_by_day(data_list)
                return min(days_dict.values()) if days_dict else 0

        elif match_today:
            data_type = match_today.group(1)
            print(f"Fetching {data_type} data for today ({today_str})")
            raw_data_csv = self.get_basic_data(data_type, today_str, today_str, user_id)
            data_list = self._parse_csv_data(raw_data_csv)
            # DAILY_TODAY implies raw, summed data for the day
            return self.dense_basic_data_to_days(data_list)

        else:
            raise ValueError(f"Unknown or invalid option format: {option}")

    def _parse_csv_data(self, csv_text: str) -> list:
        """ Parses CSV text into a list of dictionaries. """
        if not csv_text or not csv_text.strip():
            return []
        csv_lines = csv_text.strip().split('\n')
        # Check if there's actual data beyond the header
        if len(csv_lines) <= 1:
            return []
        reader = csv.DictReader(csv_lines)
        try:
            data = [row for row in reader]
            return data
        except csv.Error as e:
            print(f"CSV parsing error: {e}")
            return []

    def _group_data_by_day(self, data: list) -> dict:
        """ Groups data by day, summing values. Helper for aggregations. """
        days = {}
        for record in data:
            try:
                date = record.get("Date", "").split("T")[0]
                value_str = record.get("value")
                if date and value_str is not None:
                    value = float(value_str)
                    if date not in days:
                        days[date] = value
                    else:
                        days[date] += value
            except (ValueError, TypeError, KeyError) as e:
                print(f"Skipping record due to error: {e} - Record: {record}")
                continue
        return days

    def dense_basic_data_to_days(self, data: list) -> str:
        """ Aggregates data summing values per day. Returns JSON string like '["date": value, ...]'. """
        days = self._group_data_by_day(data)
        # Format as JSON string representing a list of key-value pairs
        dict_to_string = json.dumps([{"date": d, "value": v} for d, v in days.items()])
        return dict_to_string

    def get_user_traces(self, user_id: str, limit: int = 10):
        """
        Získá poslední doporučení (traces) pro daného uživatele z Langfuse.
        """
        # Inicializace LangfuseConnector s klíči (mohou být načteny z env nebo přímo)
        langfuse = LangfuseConnector(
            public_api_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_api_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            api_url="https://cloud.langfuse.com",
            headers={'Content-Type': 'application/json'}
        )
        all_traces = langfuse.langfuse.fetch_traces(limit=limit)
        # Filtrovat pouze pro daného uživatele podle tagu user:{user_id}
        user_tag = f"user:{user_id}"
        user_traces = [trace for trace in all_traces.data if user_tag in getattr(trace, 'tags', [])]
        return user_traces