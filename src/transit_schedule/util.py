import datetime
import json
import os

from transit_schedule.const import _LOGGER


def settings_from_file(filename: str, config: dict = None) -> str | None:
    """Reads/writes json from/to a filename."""
    if config:
        # We're writing configuration
        try:
            with open(filename, "w") as fdesc:
                fdesc.write(json.dumps(config))
                return True
        except OSError as error:
            _LOGGER.exception(error)
            return False
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename) as fdesc:
                    return json.loads(fdesc.read())
            except OSError as error:
                _LOGGER.exception(error)
                return False
        else:
            return {}


def get_modification_date(path: str):
    # Return epoch time, in UTC offset 0
    epoch = os.path.getmtime(path)

    # return datetime.datetime.fromtimestamp(epoch).strftime('%c')
    return datetime.datetime.fromtimestamp(epoch)


def is_file_expired(path: str) -> bool:
    """Checks if the file is expired. Use the last modification date if the file."""

    if not (os.path.isfile(path)):
        return True

    if os.path.getsize(path) == 0:
        _LOGGER.info(f"File {path} is zero size, considering it expired.")
        return True

    modification_date = get_modification_date(path)
    # current_date = datetime.datetime.now('UTC')
    # current_date = datetime.datetime.utcnow()
    current_date = datetime.datetime.now()
    _LOGGER.info("modification_date: " + str(modification_date))
    _LOGGER.info("current_date: " + str(current_date))

    delta = current_date - modification_date
    return delta >= datetime.timedelta(hours=24)
