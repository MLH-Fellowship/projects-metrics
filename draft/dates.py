from datetime import datetime
from pytz import timezone, utc

date_1_format = "%a %b %d %H:%M:%S %Y %z"
date_2_format = "%Y-%m-%dT%H:%M:%S%z"

date_1 = "Fri Nov 3 11:43:42 2023 +0100"
date_2 = "2023-11-02T17:43:33Z"

result_1 = datetime.strptime(date_1, date_1_format)
result_2 = datetime.strptime(date_2, date_2_format)

print(str(result_1), result_2)

result_3 = result_1.astimezone(timezone('GMT'))
print(result_3, result_2)