from datetime import datetime

def get_date() -> str:
    now: datetime = datetime.now()
    month: str = f"{now.month:02d}"
    day: str = f"{now.day:02d}"
    return '.'.join([str(now.year), month, day])

def feature_name_to_index(name):
    return name.replace('/', '-').lower().replace(':', '-')

